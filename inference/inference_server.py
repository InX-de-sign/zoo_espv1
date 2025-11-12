import cv2
import onnxruntime as ort
import numpy as np
import time
import asyncio
import httpx
import os
from fastapi import FastAPI
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Museum YOLO Inference Service")

class ArtworkDetector:
    def __init__(self, model_path):
        self.session = ort.InferenceSession(model_path)
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        height = self.input_shape[2] if isinstance(self.input_shape[2], int) else 640
        width = self.input_shape[3] if isinstance(self.input_shape[3], int) else 640
        self.input_size = (height, width)    

        # Your 3 museum artworks
        self.classes = [
            'The Progress of a Soul: The Victory',
            'The Execution of Lady Jane Grey',
            'Café Terrace at Night'
        ]
        
        self.confidence_threshold = 0.5
        self.iou_threshold = 0.4

    def preprocess(self, image):
        """Convert image to model input format"""
        img = cv2.resize(image, self.input_size)
        img = img / 255.0
        img = img.transpose(2, 0, 1)
        img = np.expand_dims(img, axis=0).astype(np.float32)
        return img

    def postprocess(self, outputs, original_shape):
        """Extract detections from model outputs"""
        try:
            predictions = outputs[0][0]  # Shape: (7, 8400)
            
            # Transpose to (8400, 7) - iterate over boxes
            predictions = predictions.T
            
            detections = []
            
            for pred in predictions:
                # pred[0:4] = bbox (cx, cy, w, h)
                # pred[4:7] = class scores (no objectness score in this model)
                
                class_scores = pred[4:7]  # 3 class scores
                class_id = np.argmax(class_scores)
                confidence = float(class_scores[class_id])
                
                if confidence < self.confidence_threshold:
                    continue
                
                # Bbox coordinates (normalized 0-1 in YOLO format)
                cx, cy, w, h = pred[0], pred[1], pred[2], pred[3]
                
                # Convert to pixel coordinates
                # YOLO coords are normalized, need to scale by input size
                cx_px = cx * self.input_size[1]
                cy_px = cy * self.input_size[0]
                w_px = w * self.input_size[1]
                h_px = h * self.input_size[0]
                
                # Convert to corner coordinates
                x1 = int(cx_px - w_px/2)
                y1 = int(cy_px - h_px/2)
                x2 = int(cx_px + w_px/2)
                y2 = int(cy_px + h_px/2)
                
                # Scale to original image size
                scale_x = original_shape[1] / self.input_size[1]
                scale_y = original_shape[0] / self.input_size[0]
                
                x1 = int(x1 * scale_x)
                y1 = int(y1 * scale_y)
                x2 = int(x2 * scale_x)
                y2 = int(y2 * scale_y)
                
                # Clip to image boundaries
                x1 = max(0, min(x1, original_shape[1]))
                y1 = max(0, min(y1, original_shape[0]))
                x2 = max(0, min(x2, original_shape[1]))
                y2 = max(0, min(y2, original_shape[0]))
                
                detections.append({
                    'class': self.classes[class_id],
                    'class_id': int(class_id),
                    'confidence': float(confidence),
                    'bbox': [x1, y1, x2, y2],
                    'timestamp': datetime.now().isoformat()
                })
            
            return detections
            
        except Exception as e:
            logger.error(f"Postprocess error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def detect(self, image):
        """Run detection on a single frame"""
        original_shape = image.shape[:2]
        input_tensor = self.preprocess(image)
        outputs = self.session.run(None, {self.input_name: input_tensor})
        detections = self.postprocess(outputs, original_shape)
        return detections

# Global state
artwork_model = None
latest_results = []
frame_count = 0
last_inference_time = 0
last_sent_detections = {}  # Track what we've sent to avoid duplicates
inference_active = False

# Configuration from environment variables
CHATBOT_URL = os.getenv("CHATBOT_URL", "http://museum_chatbot:8000")
RTSP_URL = os.getenv("RTSP_URL", "rtsp://mediamtx:8554/cam1")
MODEL_PATH = os.getenv("MODEL_PATH", "/inference/models/best_detect.onnx")
INFERENCE_INTERVAL = float(os.getenv("INFERENCE_INTERVAL", "0.5"))  # 2 FPS default
DETECTION_COOLDOWN = int(os.getenv("DETECTION_COOLDOWN", "5"))  # 5 seconds

async def send_detection_to_chatbot(label: str, confidence: float, user_id: str = "default_user"):
    """Send detection to chatbot service"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{CHATBOT_URL}/cv/detection",
                json={
                    "label": label,
                    "user_id": user_id,
                    "confidence": float(confidence)
                }
            )
            logger.info(f"✅ Sent to chatbot: {label} ({confidence:.2f}) -> {response.status_code}")
            return response.json()
    except Exception as e:
        logger.error(f"❌ Failed to send to chatbot: {e}")
        return None

def should_send_detection(label: str) -> bool:
    """Check if enough time has passed since last detection of this artwork"""
    current_time = time.time()
    
    if label not in last_sent_detections:
        last_sent_detections[label] = current_time
        return True
    
    time_since_last = current_time - last_sent_detections[label]
    if time_since_last > DETECTION_COOLDOWN:
        last_sent_detections[label] = current_time
        return True
    
    return False

def initialize_model():
    """Load ONNX model on startup"""
    global artwork_model
    try:
        logger.info(f"Loading YOLO model from {MODEL_PATH}")
        artwork_model = ArtworkDetector(MODEL_PATH)
        logger.info("✅ Artwork detection model loaded successfully")
        logger.info(f"Model classes: {artwork_model.classes}")
        return True
    except Exception as e:
        logger.error(f"❌ Error loading model: {e}")
        return False

async def process_frames():
    """Main inference loop - processes RTSP stream"""
    global latest_results, frame_count, last_inference_time, inference_active
    
    inference_active = True
    
    logger.info(f"🎥 Connecting to RTSP stream: {RTSP_URL}")
    
    cap = cv2.VideoCapture(RTSP_URL)
    
    if not cap.isOpened():
        logger.error("❌ Cannot connect to RTSP stream")
        logger.info("Waiting 5 seconds and retrying...")
        await asyncio.sleep(5)
        inference_active = False
        return
    
    logger.info("✅ Connected to RTSP stream, starting artwork detection...")
    
    try:
        while inference_active:
            ret, frame = cap.read()
            
            if not ret:
                logger.warning("Failed to read frame, reconnecting...")
                await asyncio.sleep(1)
                cap = cv2.VideoCapture(RTSP_URL)
                continue
            
            current_time = time.time()
            
            # Process frames at configured interval (default 2 FPS)
            if current_time - last_inference_time >= INFERENCE_INTERVAL:
                if artwork_model:
                    try:
                        detections = artwork_model.detect(frame)
                        latest_results = detections
                        
                        # Send detections to chatbot
                        for detection in detections:
                            label = detection['class']
                            confidence = detection['confidence']
                            
                            # Only send if cooldown period has passed
                            if should_send_detection(label):
                                logger.info(f"🎨 Detected: {label} (confidence: {confidence:.2f})")
                                await send_detection_to_chatbot(label, confidence)
                            
                        if not detections:
                            logger.debug("No artworks detected in frame")
                            
                    except Exception as e:
                        logger.error(f"Detection error: {e}")
                
                last_inference_time = current_time
                frame_count += 1
            
            # Small delay to prevent CPU overload
            await asyncio.sleep(0.01)
            
    except Exception as e:
        logger.error(f"Error in inference loop: {e}")
    finally:
        cap.release()
        inference_active = False
        logger.info("🛑 Inference loop stopped")

@app.on_event("startup")
async def startup_event():
    """Initialize model and start inference on startup"""
    if initialize_model():
        asyncio.create_task(process_frames())
        logger.info("✅ Inference service started")
    else:
        logger.error("❌ Failed to start - model not loaded")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop inference on shutdown"""
    global inference_active
    inference_active = False
    logger.info("Shutting down inference service")

# API Endpoints (FastAPI style)
@app.get("/api/detections")
async def get_detections():
    """Get latest detection results"""
    return {
        'detections': latest_results,
        'frame_count': frame_count,
        'timestamp': datetime.now().isoformat(),
        'model_loaded': artwork_model is not None,
        'inference_active': inference_active
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy' if artwork_model is not None else 'unhealthy',
        'model_loaded': artwork_model is not None,
        'model_classes': artwork_model.classes if artwork_model else [],
        'inference_active': inference_active,
        'chatbot_url': CHATBOT_URL,
        'rtsp_url': RTSP_URL
    }

@app.get("/status")
async def get_status():
    """Detailed status information"""
    return {
        "service": "YOLO Inference",
        "model_loaded": artwork_model is not None,
        "inference_active": inference_active,
        "rtsp_url": RTSP_URL,
        "chatbot_url": CHATBOT_URL,
        "inference_interval": INFERENCE_INTERVAL,
        "detection_cooldown": DETECTION_COOLDOWN,
        "frame_count": frame_count,
        "recent_detections": list(last_sent_detections.keys()),
        "latest_results": len(latest_results)
    }

@app.post("/control/start")
async def start_inference():
    """Manually start inference"""
    global inference_active
    if not inference_active and artwork_model is not None:
        asyncio.create_task(process_frames())
        return {"status": "started"}
    return {"status": "already_running" if inference_active else "model_not_loaded"}

@app.post("/control/stop")
async def stop_inference():
    """Manually stop inference"""
    global inference_active
    inference_active = False
    return {"status": "stopped"}

@app.post("/manual_detect")
async def manual_detection(label: str, confidence: float = 0.9, user_id: str = "default_user"):
    """Manually trigger a detection (for testing)"""
    try:
        result = await send_detection_to_chatbot(label, confidence, user_id)
        return {
            "status": "sent",
            "label": label,
            "confidence": confidence,
            "chatbot_response": result
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/")
async def root():
    """Root endpoint with service information"""
    detection_summary = ""
    if latest_results:
        detection_summary = "<ul>"
        for detection in latest_results:
            detection_summary += f"<li>{detection['class']} - {detection['confidence']:.2f}</li>"
        detection_summary += "</ul>"
    else:
        detection_summary = "<p>No artworks detected</p>"
    
    return f"""
    <html>
        <head>
            <title>Museum Artwork Detection</title>
            <meta http-equiv="refresh" content="2">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
                .status {{ background: #e8f5e9; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                .detection {{ background: #f0f0f0; padding: 10px; margin: 5px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎨 Museum Artwork Detection Service</h1>
                <div class="status">
                    <p><strong>Model Status:</strong> {"✅ Loaded" if artwork_model else "❌ Not Loaded"}</p>
                    <p><strong>Inference Active:</strong> {"✅ Running" if inference_active else "❌ Stopped"}</p>
                    <p><strong>Frames Processed:</strong> {frame_count}</p>
                    <p><strong>Current Detections:</strong> {len(latest_results)}</p>
                </div>
                <div class="detections">
                    <h3>Latest Detections:</h3>
                    {detection_summary}
                </div>
                <p>
                    <a href="/api/detections">View JSON API</a> | 
                    <a href="/health">System Health</a> |
                    <a href="/status">Detailed Status</a>
                </p>
            </div>
        </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Museum YOLO Inference Service")
    uvicorn.run(app, host="0.0.0.0", port=5000)