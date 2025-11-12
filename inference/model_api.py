# Museum Detection API with RTSP Camera Stream Integration
# Run with: uvicorn model_api:app --host 0.0.0.0 --port 5000

from fastapi import FastAPI, File
from fastapi.responses import HTMLResponse
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


# ==================== RTSP CAMERA STREAM ====================
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
    """Main inference loop - fetches frames from RTSP stream"""
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
    global inference_active, video_capture
    inference_active = False
    if video_capture is not None:
        video_capture.release()
    logger.info("Shutting down inference service")


# ==================== API ENDPOINTS ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with service information"""
    
    # Build detection summary
    if stream_detections:
        detection_items = "".join([
            f'<li><strong>{d["class_name"]}</strong> - {d["confidence"]:.1%} '
            f'<span style="font-size:0.85em;color:#666;">({d["timestamp"].split("T")[1][:8]})</span></li>'
            for d in stream_detections[:10]
        ])
        detection_summary = f"<ul>{detection_items}</ul>"
    else:
        detection_summary = '<p style="color:#999;font-style:italic;">No artworks detected yet</p>'
    
    # Status indicators
    model_status = "✅ Loaded" if yolo_model else "❌ Not Loaded"
    stream_status = "✅ Active" if inference_active else "⏸️ Stopped"
    status_color = "#d4edda" if (yolo_model and inference_active) else "#fff3cd"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Museum Artwork Detection</title>
        <meta http-equiv="refresh" content="3">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 1000px;
                margin: 0 auto;
                background: white;
                padding: 40px;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            h1 {{
                color: #2d3748;
                margin-bottom: 10px;
                font-size: 2.5em;
            }}
            .subtitle {{
                color: #718096;
                margin-bottom: 30px;
                font-size: 1.1em;
            }}
            .status-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                background: {status_color};
                padding: 25px;
                border-radius: 12px;
                margin-bottom: 30px;
                border-left: 5px solid #48bb78;
            }}
            .status-item {{
                display: flex;
                flex-direction: column;
            }}
            .status-label {{
                font-size: 0.9em;
                color: #4a5568;
                margin-bottom: 5px;
                font-weight: 600;
            }}
            .status-value {{
                font-size: 1.3em;
                color: #1a202c;
                font-weight: bold;
            }}
            .section {{
                background: #f7fafc;
                padding: 25px;
                border-radius: 12px;
                margin-bottom: 25px;
            }}
            .section h2 {{
                color: #2d3748;
                margin-bottom: 15px;
                font-size: 1.5em;
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .detections ul {{
                list-style: none;
                margin-top: 15px;
            }}
            .detections li {{
                padding: 12px;
                margin: 8px 0;
                background: white;
                border-radius: 8px;
                border-left: 4px solid #667eea;
                transition: transform 0.2s;
            }}
            .detections li:hover {{
                transform: translateX(5px);
            }}
            .endpoints {{
                display: grid;
                gap: 10px;
            }}
            .endpoint {{
                background: white;
                padding: 15px;
                border-radius: 8px;
                border-left: 4px solid #3182ce;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .endpoint code {{
                background: #edf2f7;
                padding: 6px 12px;
                border-radius: 6px;
                font-family: 'Courier New', monospace;
                font-weight: bold;
                color: #2d3748;
            }}
            .endpoint-desc {{
                color: #718096;
                font-size: 0.95em;
            }}
            .refresh-note {{
                text-align: center;
                color: #a0aec0;
                font-size: 0.9em;
                margin-top: 20px;
                padding: 10px;
                background: #edf2f7;
                border-radius: 8px;
            }}
            .badge {{
                display: inline-block;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 0.85em;
                font-weight: 600;
            }}
            .badge-success {{ background: #c6f6d5; color: #22543d; }}
            .badge-warning {{ background: #feebc8; color: #7c2d12; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎨 Museum Artwork Detection</h1>
            <p class="subtitle">Real-time YOLO-based artwork detection system</p>
            
            <div class="status-grid">
                <div class="status-item">
                    <span class="status-label">🤖 Model</span>
                    <span class="status-value">{model_status}</span>
                </div>
                <div class="status-item">
                    <span class="status-label">📹 Stream</span>
                    <span class="status-value">{stream_status}</span>
                </div>
                <div class="status-item">
                    <span class="status-label">📊 Frames</span>
                    <span class="status-value">{frame_count:,}</span>
                </div>
                <div class="status-item">
                    <span class="status-label">🎯 Detections</span>
                    <span class="status-value">{len(stream_detections)}</span>
                </div>
            </div>
            
            <div class="section detections">
                <h2>🔍 Latest Detections</h2>
                {detection_summary}
            </div>
            
            <div class="section">
                <h2>📡 API Endpoints</h2>
                <div class="endpoints">
                    <div class="endpoint">
                        <code>GET /health</code>
                        <span class="endpoint-desc">Health check</span>
                    </div>
                    <div class="endpoint">
                        <code>GET /api/detections</code>
                        <span class="endpoint-desc">Stream detections (JSON)</span>
                    </div>
                    <div class="endpoint">
                        <code>POST /predict/</code>
                        <span class="endpoint-desc">Upload image</span>
                    </div>
                    <div class="endpoint">
                        <code>GET /result/</code>
                        <span class="endpoint-desc">Get upload results</span>
                    </div>
                    <div class="endpoint">
                        <code>GET /debug</code>
                        <span class="endpoint-desc">Debug info</span>
                    </div>
                    <div class="endpoint">
                        <code>POST /control/start</code>
                        <span class="endpoint-desc">Start inference</span>
                    </div>
                    <div class="endpoint">
                        <code>POST /control/stop</code>
                        <span class="endpoint-desc">Stop inference</span>
                    </div>
                </div>
            </div>
            
            <div class="refresh-note">
                🔄 Page auto-refreshes every 3 seconds
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content


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
    
    # Test camera (for RTSP, we can't use httpx)
    camera_status = "RTSP stream configured"
    if video_capture is not None and video_capture.isOpened():
        camera_status = "connected and active"
    elif video_capture is not None:
        camera_status = "initialized but not opened"
    else:
        camera_status = "not initialized"
    
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