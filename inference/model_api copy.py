# Museum Detection API with HTTP Camera Stream Integration
# Run with: uvicorn model_api:app --host 0.0.0.0 --port 5000

from fastapi import FastAPI, File
from ultralytics import YOLO
from PIL import Image
import numpy as np
import asyncio
import httpx
import time
import io
import os
import cv2
import logging
from datetime import datetime

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
video_capture = None

# Configuration from environment variables
YOLO_MODEL_PATH = os.getenv("MODEL_PATH", "/app/models/best.onnx")
CHATBOT_URL = os.getenv("CHATBOT_URL", "http://museum_chatbot:8000")
CAMERA_STREAM_URL = os.getenv("CAMERA_URL", "rtsp://mediamtx:8554/cam1")
INFERENCE_INTERVAL = float(os.getenv("INFERENCE_INTERVAL", "0.5"))
DETECTION_COOLDOWN = int(os.getenv("DETECTION_COOLDOWN", "5"))

# FastAPI app
app = FastAPI(title="Museum YOLO Inference Service")

# Global state
yolo_model = None
stream_detections = []
upload_prediction = None
last_prediction_time = 0
frame_count = 0
last_sent_detections = {}
inference_active = False


# ==================== MODEL LOADING ====================
def load_model():
    """Load YOLO model and warm up"""
    global yolo_model
    try:
        logger.info(f"Loading YOLO model from {YOLO_MODEL_PATH}")
        yolo_model = YOLO(YOLO_MODEL_PATH, task='detect')
        
        # Warm up
        width, height = 256, 256
        dummy_img = Image.fromarray(
            np.random.randint(0, 256, (height, width, 3), dtype=np.uint8), 'RGB'
        )
        _ = yolo_model([dummy_img])
        
        logger.info("✅ YOLO model loaded successfully")
        logger.info(f"Model classes: {list(yolo_model.names.values())}")
        return True
    except Exception as e:
        logger.error(f"❌ Error loading model: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# ==================== CHATBOT INTEGRATION ====================
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
    except httpx.ConnectError as e:
        logger.error(f"❌ Cannot connect to chatbot at {CHATBOT_URL}: {e}")
        return None
    except httpx.TimeoutException:
        logger.error(f"❌ Chatbot request timeout")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to send to chatbot: {e}")
        return None


def should_send_detection(label: str) -> bool:
    """Check if enough time has passed since last detection"""
    current_time = time.time()
    
    if label not in last_sent_detections:
        last_sent_detections[label] = current_time
        return True
    
    time_since_last = current_time - last_sent_detections[label]
    if time_since_last > DETECTION_COOLDOWN:
        last_sent_detections[label] = current_time
        return True
    
    return False


# ==================== HTTP CAMERA STREAM ====================
# async def fetch_camera_frame():
#     """Fetch a single frame from HTTP/HTTPS camera endpoint"""
#     try:
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             response = await client.get(CAMERA_STREAM_URL)
            
#             if response.status_code == 200:
#                 image_data = io.BytesIO(response.content)
#                 pil_image = Image.open(image_data)
#                 return pil_image
#             else:
#                 logger.error(f"Camera returned status {response.status_code}")
#                 return None
                
#     except httpx.ConnectError as e:
#         logger.warning(f"Cannot connect to camera at {CAMERA_STREAM_URL}: {e}")
#         return None
#     except httpx.TimeoutException:
#         logger.warning(f"Camera request timeout")
#         return None
#     except Exception as e:
#         logger.error(f"Error fetching frame: {e}")
#         return None

async def fetch_camera_frame():
    """Fetch a frame from RTSP stream"""
    global video_capture
    
    try:
        # Initialize video capture if needed
        if video_capture is None or not video_capture.isOpened():
            logger.info(f"Opening video stream: {CAMERA_STREAM_URL}")
            video_capture = cv2.VideoCapture(CAMERA_STREAM_URL)
            
            if not video_capture.isOpened():
                logger.error("Failed to open video stream")
                return None
        
        # Read frame
        ret, frame = video_capture.read()
        
        if not ret or frame is None:
            logger.warning("Failed to read frame")
            video_capture.release()
            video_capture = None
            return None
        
        # Convert BGR to RGB and to PIL Image
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        return pil_image
        
    except Exception as e:
        logger.error(f"Error fetching frame: {e}")
        if video_capture is not None:
            video_capture.release()
            video_capture = None
        return None


async def process_http_stream():
    """Main inference loop - fetches frames via HTTP"""
    global stream_detections, frame_count, inference_active
    
    inference_active = True
    last_inference_time = 0
    retry_count = 0
    max_retries = 3
    
    logger.info(f"🎥 Camera stream configured: {CAMERA_STREAM_URL}")
    logger.info(f"📡 Chatbot endpoint: {CHATBOT_URL}")
    
    # Test initial connection
    logger.info("Testing camera connection...")
    test_frame = await fetch_camera_frame()
    if test_frame is None:
        logger.warning("⚠️ Cannot connect to camera (will retry in background)")
        # Don't stop - keep trying
    else:
        logger.info("✅ Camera connected successfully")
    
    try:
        while inference_active:
            current_time = time.time()
            
            if current_time - last_inference_time >= INFERENCE_INTERVAL:
                
                frame = await fetch_camera_frame()
                
                if frame is None:
                    retry_count += 1
                    if retry_count <= max_retries:
                        logger.debug(f"Waiting for camera... (attempt {retry_count})")
                    await asyncio.sleep(2)
                    last_inference_time = current_time
                    continue
                
                retry_count = 0
                
                if yolo_model:
                    try:
                        results = yolo_model([frame])
                        detections = parse_yolo_results(results)
                        stream_detections = detections
                        
                        for detection in detections:
                            label = detection['class_name']
                            confidence = detection['confidence']
                            
                            if should_send_detection(label):
                                logger.info(f"🎨 Detected: {label} (confidence: {confidence:.2f})")
                                await send_detection_to_chatbot(label, confidence)
                        
                        if detections:
                            logger.debug(f"Frame {frame_count}: {len(detections)} detections")
                            
                    except Exception as e:
                        logger.error(f"Detection error: {e}")
                
                last_inference_time = current_time
                frame_count += 1
                
                if frame_count % 50 == 0:
                    logger.info(f"📊 Processed {frame_count} frames")
            
            await asyncio.sleep(0.1)
            
    except Exception as e:
        logger.error(f"Error in inference loop: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        inference_active = False
        logger.info("🛑 Inference loop stopped")


def parse_yolo_results(results):
    """Parse YOLO results into standard format"""
    detections = []
    
    if results[0].boxes is not None and len(results[0].boxes) > 0:
        classes = results[0].boxes.cls.int().cpu().numpy()
        confidences = results[0].boxes.conf.cpu().numpy()
        bboxes = results[0].boxes.xyxy.cpu().numpy()
        
        for cls_idx, conf, bbox in zip(classes, confidences, bboxes):
            detections.append({
                "class_name": results[0].names[cls_idx.item()],
                "class_id": int(cls_idx.item()),
                "confidence": float(conf),
                "bbox": bbox.tolist(),
                "timestamp": datetime.now().isoformat()
            })
        
        detections.sort(key=lambda x: x["confidence"], reverse=True)
    
    return detections


# ==================== FASTAPI LIFECYCLE ====================
@app.on_event("startup")
async def startup_event():
    """Initialize model and start stream processing"""
    logger.info("🚀 Starting Museum Detection Service")
    logger.info(f"Configuration:")
    logger.info(f"  - Model: {YOLO_MODEL_PATH}")
    logger.info(f"  - Chatbot: {CHATBOT_URL}")
    logger.info(f"  - Camera: {CAMERA_STREAM_URL}")
    logger.info(f"  - Inference Interval: {INFERENCE_INTERVAL}s")
    logger.info(f"  - Detection Cooldown: {DETECTION_COOLDOWN}s")
    
    if load_model():
        # Test chatbot connection
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{CHATBOT_URL}/health")
                logger.info(f"✅ Chatbot connected: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Chatbot not reachable yet: {e}")
        
        asyncio.create_task(process_http_stream())
        logger.info("✅ Inference service started")
    else:
        logger.error("❌ Failed to start - model not loaded")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop inference on shutdown"""
    global inference_active
    inference_active = False
    logger.info("Shutting down inference service")


# ==================== API ENDPOINTS ====================

@app.get("/")
async def root():
    """Root endpoint with service information"""
    detection_summary = ""
    if stream_detections:
        detection_summary = "<ul>"
        for detection in stream_detections:
            detection_summary += f"<li><strong>{detection['class_name']}</strong> - {detection['confidence']:.2%}</li>"
        detection_summary += "</ul>"
    else:
        detection_summary = "<p><em>No artworks detected yet</em></p>"
    
    status_color = "#e8f5e9" if (yolo_model and inference_active) else "#fff3cd"
    
    return f"""
    <html>
        <head>
            <title>Museum Artwork Detection</title>
            <meta http-equiv="refresh" content="3">
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                h1 {{ color: #333; margin-top: 0; }}
                .status {{ background: {status_color}; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                .status p {{ margin: 8px 0; }}
                .endpoint {{ background: #f8f9fa; padding: 12px; margin: 8px 0; border-radius: 6px; border-left: 4px solid #007bff; }}
                .endpoint code {{ background: #e9ecef; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
                .detections {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                ul {{ margin: 10px 0; }}
                li {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎨 Museum Artwork Detection Service</h1>
                
                <div class="status">
                    <p><strong>🤖 Model:</strong> {"✅ Loaded" if yolo_model else "❌ Not Loaded"}</p>
                    <p><strong>📹 Stream:</strong> {"✅ Active" if inference_active else "⏸️ Stopped"}</p>
                    <p><strong>📊 Frames Processed:</strong> {frame_count:,}</p>
                    <p><strong>🎯 Current Detections:</strong> {len(stream_detections)}</p>
                </div>
                
                <div class="detections">
                    <h3>Latest Detections:</h3>
                    {detection_summary}
                    <p style="font-size: 0.9em; color: #666; margin-top: 10px;">
                        <em>Auto-refreshes every 3 seconds</em>
                    </p>
                </div>
                
                <h3>📡 API Endpoints:</h3>
                <div class="endpoint">
                    <code>GET /health</code> - Health check
                </div>
                <div class="endpoint">
                    <code>GET /api/detections</code> - Get stream detections (JSON)
                </div>
                <div class="endpoint">
                    <code>POST /predict/</code> - Upload image for detection
                </div>
                <div class="endpoint">
                    <code>GET /result/</code> - Get results from uploaded image
                </div>
                <div class="endpoint">
                    <code>GET /debug</code> - Debug information
                </div>
                <div class="endpoint">
                    <code>POST /control/start</code> - Start inference
                </div>
                <div class="endpoint">
                    <code>POST /control/stop</code> - Stop inference
                </div>
            </div>
        </body>
    </html>
    """


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy' if yolo_model is not None else 'unhealthy',
        'model_loaded': yolo_model is not None,
        'inference_active': inference_active,
        'frames_processed': frame_count,
        'chatbot_url': CHATBOT_URL,
        'camera_url': CAMERA_STREAM_URL
    }


@app.get("/api/detections")
async def get_stream_detections():
    """Get latest detections from camera stream"""
    return {
        'detections': stream_detections,
        'frame_count': frame_count,
        'timestamp': datetime.now().isoformat(),
        'model_loaded': yolo_model is not None,
        'inference_active': inference_active
    }


@app.post("/predict/")
async def predict_uploaded_image(image: bytes = File(...)):
    """Upload an image for prediction"""
    global upload_prediction, last_prediction_time
    
    if yolo_model is None:
        return {"status": "error", "message": "Model not loaded"}
    
    try:
        pil_image = Image.open(io.BytesIO(image))
        results = yolo_model([pil_image])
        upload_prediction = results
        last_prediction_time = time.time()
        
        return {
            "status": "success",
            "message": "Image processed successfully",
            "timestamp": last_prediction_time
        }
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/result/")
async def get_uploaded_result():
    """Get results from last uploaded image"""
    if upload_prediction is None:
        return {
            "detections": [],
            "timestamp": None,
            "message": "No prediction available. Upload an image via POST /predict/"
        }
    
    detections = parse_yolo_results(upload_prediction)
    return {
        "detections": detections,
        "timestamp": last_prediction_time,
        "total_objects": len(detections)
    }


@app.post("/control/start")
async def start_inference():
    """Manually start stream inference"""
    global inference_active
    if not inference_active and yolo_model is not None:
        asyncio.create_task(process_http_stream())
        return {"status": "started"}
    return {"status": "already_running" if inference_active else "model_not_loaded"}


@app.post("/control/stop")
async def stop_inference():
    """Manually stop stream inference"""
    global inference_active
    inference_active = False
    return {"status": "stopped"}


@app.get("/debug")
async def debug_info():
    """Detailed debug information"""
    
    # Test camera
    camera_status = "testing..."
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(CAMERA_STREAM_URL)
            camera_status = f"reachable (HTTP {response.status_code})"
    except httpx.ConnectError:
        camera_status = "unreachable (connection refused)"
    except httpx.TimeoutException:
        camera_status = "unreachable (timeout)"
    except Exception as e:
        camera_status = f"error ({type(e).__name__})"
    
    # Test chatbot
    chatbot_status = "testing..."
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{CHATBOT_URL}/health")
            chatbot_status = f"reachable (HTTP {response.status_code})"
    except httpx.ConnectError:
        chatbot_status = "unreachable (connection refused)"
    except httpx.TimeoutException:
        chatbot_status = "unreachable (timeout)"
    except Exception as e:
        chatbot_status = f"error ({type(e).__name__})"
    
    return {
        "service": "Museum Detection Service",
        "timestamp": datetime.now().isoformat(),
        "model": {
            "loaded": yolo_model is not None,
            "path": YOLO_MODEL_PATH,
            "classes": list(yolo_model.names.values()) if yolo_model else []
        },
        "camera": {
            "url": CAMERA_STREAM_URL,
            "status": camera_status,
            "frames_processed": frame_count
        },
        "chatbot": {
            "url": CHATBOT_URL,
            "status": chatbot_status,
            "recent_detections_sent": list(last_sent_detections.keys())
        },
        "inference": {
            "active": inference_active,
            "interval_seconds": INFERENCE_INTERVAL,
            "cooldown_seconds": DETECTION_COOLDOWN
        },
        "detections": {
            "current_count": len(stream_detections),
            "latest": stream_detections[:5] if stream_detections else []
        }
    }


@app.post("/manual_detect")
async def manual_detection(label: str, confidence: float = 0.9, user_id: str = "default_user"):
    """Manually trigger a detection (for testing chatbot integration)"""
    logger.info(f"Manual detection triggered: {label} ({confidence})")
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


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Museum Detection Service")
    uvicorn.run(app, host="0.0.0.0", port=5000)