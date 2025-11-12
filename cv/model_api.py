# model_api.py - Server side for receiving frames from webcam_client.py
from fastapi import FastAPI, File, UploadFile
from typing import Annotated
from ultralytics import YOLO
from PIL import Image
import numpy as np
import threading
import time
import io
import os
import logging
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

MODEL_PATH = os.getenv("MODEL_PATH", "models/best.onnx")
CHATBOT_URL = os.getenv("CHATBOT_URL", "http://museum_chatbot:8000")
DETECTION_COOLDOWN = float(os.getenv("DETECTION_COOLDOWN", "5"))  # seconds between sending same detection

# Detection parameters (matching your working local setup)
IMGSZ = int(os.getenv("IMGSZ", "640"))  # Image size for inference
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.75"))  # Confidence threshold (same as your working code)
DEVICE = os.getenv("DEVICE", "cpu")  # Use CPU for inference

# =============================================================================
# LOAD YOLO MODEL
# =============================================================================

logger.info(f"Loading YOLO model from {MODEL_PATH}")
yolo_model = YOLO(MODEL_PATH, task='detect')

# Warm up model with exact same parameters as inference
logger.info("Warming up YOLO model...")
width, height = 640, 640
random_img = Image.fromarray(np.random.randint(0, 256, (height, width, 3), dtype=np.uint8), 'RGB')
warmup_result = yolo_model.predict(source=random_img, imgsz=IMGSZ, conf=CONF_THRESHOLD, device=DEVICE, verbose=False)
logger.info(f"✅ YOLO model loaded successfully")
logger.info(f"Model classes: {list(yolo_model.names.values())}")
logger.info(f"Detection settings: imgsz={IMGSZ}, conf={CONF_THRESHOLD}, device={DEVICE}")

# =============================================================================
# GLOBAL STATE
# =============================================================================

prediction = None
last_prediction_time = 0
frames_processed = 0

new_img = False
predicting = False

img = None
img_buffer = None

# Detection tracking for cooldown
last_detections = {}  # {class_name: timestamp}

# =============================================================================
# PREDICTION THREAD
# =============================================================================

def prediction_loop():
    """Background thread for processing incoming frames"""
    global predicting, img_buffer, img, new_img, prediction, last_prediction_time, frames_processed
    
    logger.info("🔄 Prediction loop started")
    
    while True:
        if new_img:
            predicting = True
            img = img_buffer
            img_buffer = None
            new_img = False

            try:
                # Perform prediction with EXACT same settings as your working local code
                # imgsz=640, conf=0.75, device="cpu"
                prediction = yolo_model.predict(
                    source=img, 
                    imgsz=IMGSZ, 
                    conf=CONF_THRESHOLD, 
                    device=DEVICE,
                    verbose=False
                )
                last_prediction_time = time.time()
                frames_processed += 1
                
                # DETAILED LOGGING FOR DEBUGGING
                print("\n" + "="*80)
                print(f"🔍 FRAME #{frames_processed} PROCESSED at {time.strftime('%H:%M:%S')}")
                print("="*80)
                
                # Log detection results
                if prediction[0].boxes is not None and len(prediction[0].boxes) > 0:
                    classes = prediction[0].boxes.cls.int().cpu().numpy()
                    confidences = prediction[0].boxes.conf.cpu().numpy()
                    bboxes = prediction[0].boxes.xyxy.cpu().numpy()
                    
                    print(f"✅ DETECTIONS FOUND: {len(classes)} object(s)")
                    print("-"*80)
                    
                    for idx, (cls_idx, conf, bbox) in enumerate(zip(classes, confidences, bboxes)):
                        class_name = prediction[0].names[cls_idx.item()]
                        print(f"  #{idx+1}: {class_name}")
                        print(f"       Confidence: {conf:.4f} ({conf*100:.2f}%)")
                        print(f"       BBox: [{bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f}]")
                        logger.info(f"🎯 Detected: {class_name} (confidence: {conf:.2f})")
                    
                    print("-"*80)
                    
                    # Send detections to chatbot (with cooldown)
                    send_detections_to_chatbot(prediction[0])
                else:
                    print("❌ NO DETECTIONS - Frame processed but no objects found")
                    print(f"   Image size: {img.size if hasattr(img, 'size') else 'unknown'}")
                    print(f"   Model expects classes: {list(yolo_model.names.values())}")
                    logger.debug("No objects detected in frame")
                
                print("="*80 + "\n")
                
            except Exception as e:
                print(f"\n❌ PREDICTION ERROR: {e}")
                logger.error(f"❌ Prediction error: {e}", exc_info=True)
            
            predicting = False
        
        time.sleep(0.1)  # Sleep briefly to avoid busy-waiting


def send_detections_to_chatbot(result):
    """Send detected objects to chatbot with cooldown"""
    global last_detections
    
    if result.boxes is None or len(result.boxes) == 0:
        return
    
    current_time = time.time()
    classes = result.boxes.cls.int().cpu().numpy()
    confidences = result.boxes.conf.cpu().numpy()
    
    # Find highest confidence detection
    max_conf_idx = np.argmax(confidences)
    class_idx = classes[max_conf_idx]
    confidence = confidences[max_conf_idx]
    class_name = result.names[class_idx.item()]
    
    # Check cooldown
    if class_name in last_detections:
        time_since_last = current_time - last_detections[class_name]
        if time_since_last < DETECTION_COOLDOWN:
            logger.debug(f"⏳ Cooldown active for {class_name} ({time_since_last:.1f}s)")
            return
    
    # Send to chatbot
    try:
        logger.info(f"📡 Sending detection to chatbot: {class_name} ({confidence:.2f})")
        
        payload = {
            "artwork_name": class_name,
            "confidence": float(confidence),
            "timestamp": current_time
        }
        
        with httpx.Client() as client:
            response = client.post(
                f"{CHATBOT_URL}/api/artwork/detected",
                json=payload,
                timeout=5.0
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Chatbot notified: {class_name}")
                last_detections[class_name] = current_time
            else:
                logger.warning(f"⚠️ Chatbot responded with {response.status_code}")
                
    except Exception as e:
        logger.error(f"❌ Failed to notify chatbot: {e}")


# Start the prediction loop in a separate thread
threading.Thread(target=prediction_loop, daemon=True).start()

# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(title="YOLO Inference API", version="1.0")

@app.on_startup
async def startup_event():
    """Initialize connections on startup"""
    logger.info("="*60)
    logger.info("🚀 YOLO Inference Service Starting")
    logger.info("="*60)
    logger.info(f"Model: {MODEL_PATH}")
    logger.info(f"Image Size: {IMGSZ}")
    logger.info(f"Confidence Threshold: {CONF_THRESHOLD}")
    logger.info(f"Device: {DEVICE}")
    logger.info(f"Chatbot: {CHATBOT_URL}")
    logger.info(f"Detection Cooldown: {DETECTION_COOLDOWN}s")
    logger.info("="*60)
    
    # Test chatbot connection
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{CHATBOT_URL}/health", timeout=5.0)
            if response.status_code == 200:
                logger.info(f"✅ Chatbot connected: {response.status_code}")
            else:
                logger.warning(f"⚠️ Chatbot responded with {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Cannot connect to chatbot: {e}")
    
    logger.info("✅ Inference service ready to receive frames from Raspberry Pi")


@app.get("/")
async def root():
    """Root endpoint - returns warmup test result"""
    if warmup_result[0].boxes is not None and len(warmup_result[0].boxes) > 0:
        classes = warmup_result[0].boxes.cls.int().cpu().numpy()
        confidences = warmup_result[0].boxes.conf.cpu().numpy()
        
        detections = []
        for cls_idx, conf in zip(classes, confidences):
            detections.append({
                "class_name": warmup_result[0].names[cls_idx.item()],
                "confidence": float(conf)
            })
        
        detections.sort(key=lambda x: x["confidence"], reverse=True)
        return {"detections": detections}
    else:
        return {"detections": [], "message": "Model loaded, waiting for frames"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": True,
        "frames_processed": frames_processed,
        "chatbot_url": CHATBOT_URL,
        "last_prediction": last_prediction_time if last_prediction_time > 0 else None
    }


@app.post("/predict/")
async def predict(image: Annotated[bytes, File()]):
    """
    Receive frame from webcam_client.py and queue for prediction
    
    This endpoint is called by the Raspberry Pi webcam_client
    """
    global predicting, img_buffer, new_img
    
    try:
        # Open image and convert to RGB (important for consistency)
        img_pil = Image.open(io.BytesIO(image))
        
        # Convert to RGB if needed (same as cv2 BGR->RGB conversion)
        if img_pil.mode != 'RGB':
            img_pil = img_pil.convert('RGB')
        
        img_buffer = img_pil
        new_img = True
        
        print(f"📥 Frame received: {len(image)} bytes, size={img_pil.size}, mode={img_pil.mode}")
        logger.debug(f"📥 Frame received (size: {len(image)} bytes)")
        return {
            "status": "success",
            "message": "Image received for prediction",
            "frames_processed": frames_processed
        }
    except Exception as e:
        print(f"❌ Error receiving frame: {e}")
        logger.error(f"❌ Error receiving frame: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/result/")
async def get_result():
    """
    Get latest prediction results
    
    Returns the most recent detection results from processed frames
    """
    global prediction, last_prediction_time
    
    if prediction is None:
        return {
            "detections": [],
            "timestamp": None,
            "frames_processed": frames_processed,
            "message": "No prediction available yet"
        }
    
    # Check if prediction has results
    if prediction[0].boxes is not None and len(prediction[0].boxes) > 0:
        classes = prediction[0].boxes.cls.int().cpu().numpy()
        confidences = prediction[0].boxes.conf.cpu().numpy()
        bboxes = prediction[0].boxes.xyxy.cpu().numpy()
        
        detections = []
        for cls_idx, conf, bbox in zip(classes, confidences, bboxes):
            detections.append({
                "class_name": prediction[0].names[cls_idx.item()],
                "confidence": float(conf),
                "bbox": bbox.tolist()  # [x1, y1, x2, y2]
            })
        
        # Sort by confidence in descending order
        detections.sort(key=lambda x: x["confidence"], reverse=True)
        
        return {
            "detections": detections,
            "timestamp": last_prediction_time,
            "frames_processed": frames_processed,
            "total_objects": len(detections)
        }
    else:
        return {
            "detections": [],
            "timestamp": last_prediction_time,
            "frames_processed": frames_processed,
            "total_objects": 0,
            "message": "No objects detected in the latest frame"
        }


@app.get("/stats/")
async def get_stats():
    """Get inference statistics"""
    return {
        "frames_processed": frames_processed,
        "last_prediction_time": last_prediction_time,
        "model_path": MODEL_PATH,
        "chatbot_url": CHATBOT_URL,
        "detection_cooldown": DETECTION_COOLDOWN,
        "tracked_detections": list(last_detections.keys()),
        "is_predicting": predicting
    }