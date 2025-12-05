# Zoo Animal Detection API with ESP32 Batch Camera & RTSP Stream Integration
# Run with: uvicorn model_api:app --host 0.0.0.0 --port 5000

from fastapi import FastAPI, File, UploadFile, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import WebSocket, WebSocketDisconnect
from image_receiver import ImageWebSocketReceiver
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
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from io import BytesIO
from typing import List

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
video_capture = None

# Configuration from environment variables
YOLO_MODEL_PATH = os.getenv("MODEL_PATH", "/app/models/best_animal_v3.onnx")
CHATBOT_URL = os.getenv("CHATBOT_URL", "http://zoo_chatbot:8000")
CAMERA_STREAM_URL = os.getenv("CAMERA_URL", "rtsp://mediamtx:8554/cam1")
INFERENCE_INTERVAL = float(os.getenv("INFERENCE_INTERVAL", "0.5"))
DETECTION_COOLDOWN = int(os.getenv("DETECTION_COOLDOWN", "5"))

# FastAPI app
app = FastAPI(title="Zoo Animal Detection Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

image_receiver = ImageWebSocketReceiver()

# Global state
yolo_model = None
stream_detections = []
upload_prediction = None
last_prediction_time = 0
frame_count = 0
last_sent_detections = {}
inference_active = False

# 8 animal classes from your trained model
ANIMAL_CLASSES = [
    'arctic-fox',
    'capybara', 
    'harbor-seal',
    'panda',
    'parrot',
    'penguin',
    'red-panda',
    'sloth'
]


# ==================== MODEL LOADING ====================
def load_model():
    """Load YOLO model and warm up"""
    global yolo_model
    try:
        logger.info(f"Loading YOLO animal detection model from {YOLO_MODEL_PATH}")
        yolo_model = YOLO(YOLO_MODEL_PATH, task='detect')
        
        # Warm up
        width, height = 256, 256
        dummy_img = Image.fromarray(
            np.random.randint(0, 256, (height, width, 3), dtype=np.uint8), 'RGB'
        )
        _ = yolo_model([dummy_img])
        
        logger.info("✅ YOLO animal detection model loaded successfully")
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


# ==================== ESP32 CAMERA INFERENCE ====================
async def run_inference_on_image(image: Image.Image, client_id: str):
    """Run YOLO inference on received image from ESP32"""
    if yolo_model is None:
        return []
    
    try:
        results = yolo_model([image])
        detections = parse_yolo_results(results)
        
        # Send to chatbot if detections found
        for detection in detections:
            label = detection['class_name']
            confidence = detection['confidence']
            
            if should_send_detection(label):
                logger.info(f"� ESP32 Camera detected: {label} ({confidence:.2f})")
                await send_detection_to_chatbot(label, confidence, client_id)
        
        return detections
        
    except Exception as e:
        logger.error(f"Inference error: {e}")
        return []

# Set the inference callback for ESP32 images
image_receiver.inference_callback = run_inference_on_image


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


# ==================== RTSP STREAM PROCESSING ====================
async def capture_and_process_stream():
    """Background task to capture and process RTSP stream"""
    global video_capture, inference_active, frame_count, stream_detections
    
    logger.info(f"📹 Starting RTSP stream capture from: {CAMERA_STREAM_URL}")
    
    video_capture = cv2.VideoCapture(CAMERA_STREAM_URL)
    
    if not video_capture.isOpened():
        logger.error(f"❌ Failed to open camera stream: {CAMERA_STREAM_URL}")
        return
    
    logger.info("✅ RTSP camera stream opened successfully")
    inference_active = True
    
    while inference_active:
        try:
            ret, frame = video_capture.read()
            
            if not ret:
                logger.warning("⚠️ Failed to read frame from stream")
                await asyncio.sleep(1.0)
                continue
            
            frame_count += 1
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)
            
            # Run inference
            if yolo_model is not None:
                results = yolo_model([pil_image])
                detections = parse_yolo_results(results)
                
                if detections:
                    logger.info(f"🎯 Frame {frame_count}: {len(detections)} animals detected")
                    stream_detections = detections
                    
                    # Send to chatbot
                    for detection in detections:
                        label = detection['class_name']
                        confidence = detection['confidence']
                        
                        if should_send_detection(label):
                            logger.info(f"� RTSP Stream detected: {label} ({confidence:.2f})")
                            await send_detection_to_chatbot(label, confidence, "rtsp_camera")
            
            # Inference interval
            await asyncio.sleep(INFERENCE_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error processing stream frame: {e}")
            await asyncio.sleep(1.0)
    
    if video_capture is not None:
        video_capture.release()
    logger.info("📹 RTSP stream processing stopped")


# ==================== FASTAPI LIFECYCLE ====================
@app.on_event("startup")
async def startup_event():
    """Initialize model and start stream processing"""
    logger.info("🚀 Starting Zoo Animal Detection Service")
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
        
        # Start RTSP stream processing
        asyncio.create_task(capture_and_process_stream())
        
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


# ==================== BATCH UPLOAD ENDPOINT (FIXED) ====================
@app.post("/vision/upload_batch")
async def upload_batch_images(
    file1: bytes = File(...),
    file2: bytes = File(...),
    file3: bytes = File(...),
    file4: bytes = File(...),
    x_client_id: str = Header(None),
    x_timestamp: str = Header(None)
):
    """
    Batch upload endpoint for 4 images from ESP32
    Processes all 4 images together and returns combined results
    """
    try:
        client_id = x_client_id or "unknown_camera"
        timestamp = x_timestamp or datetime.now().isoformat()
        
        files = [file1, file2, file3, file4]
        
        logger.info(f"📦 Received batch upload from {client_id}: {len(files)} images")
        
        # Process all images
        all_detections = []
        batch_results = []
        
        for idx, file_bytes in enumerate(files):
            try:
                # Convert to PIL Image
                image = Image.open(BytesIO(file_bytes))
                logger.info(f"📸 Image {idx+1}: {image.size[0]}x{image.size[1]} {image.mode}, size={len(file_bytes)} bytes")
                
                # Run YOLO inference
                if yolo_model is not None:
                    results = yolo_model([image])
                    detections = parse_yolo_results(results)
                    
                    batch_results.append({
                        "image_index": idx + 1,
                        "image_size": f"{image.size[0]}x{image.size[1]}",
                        "detections": detections,
                        "detection_count": len(detections)
                    })
                    
                    # Collect all detections
                    all_detections.extend(detections)
                    
                    logger.info(f"✅ Image {idx+1}: {len(detections)} detections")
                else:
                    batch_results.append({
                        "image_index": idx + 1,
                        "error": "Model not loaded"
                    })
                    
            except Exception as e:
                logger.error(f"❌ Error processing image {idx+1}: {e}")
                batch_results.append({
                    "image_index": idx + 1,
                    "error": str(e)
                })
        
        # Send unique detections to chatbot
        unique_animals = {}
        for detection in all_detections:
            label = detection['class_name']
            confidence = detection['confidence']
            
            # Keep highest confidence for each animal
            if label not in unique_animals or confidence > unique_animals[label]:
                unique_animals[label] = confidence
        
        # Send to chatbot with cooldown check
        sent_to_chatbot = []
        for label, confidence in unique_animals.items():
            if should_send_detection(label):
                logger.info(f"🦊 Batch detected: {label} ({confidence:.2f})")
                chatbot_response = await send_detection_to_chatbot(label, confidence, client_id)
                sent_to_chatbot.append({
                    "animal": label,
                    "confidence": confidence,
                    "sent": chatbot_response is not None
                })
        
        return JSONResponse({
            "status": "success",
            "client_id": client_id,
            "timestamp": timestamp,
            "batch_size": len(files),
            "total_detections": len(all_detections),
            "unique_animals": list(unique_animals.keys()),
            "sent_to_chatbot": sent_to_chatbot,
            "results": batch_results
        })
        
    except Exception as e:
        logger.error(f"❌ Batch upload error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/upload_batch")
async def upload_batch_no_prefix(
    file1: bytes = File(...),
    file2: bytes = File(...),
    file3: bytes = File(...),
    file4: bytes = File(...),
    x_client_id: str = Header(None),
    x_timestamp: str = Header(None)
):
    """Batch upload without /vision prefix (for ESP32 compatibility)"""
    logger.info("📍 Request at /upload_batch (no prefix)")
    return await upload_batch_images(file1, file2, file3, file4, x_client_id, x_timestamp)
        
# ==================== API ENDPOINTS ====================
@app.websocket("/vision/ws/esp32/camera/{client_id}")
async def websocket_camera_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for ESP32 camera clients"""
    logger.info(f"📷 Camera WebSocket connection from: {client_id}")
    logger.info(f"   Client: {websocket.client}")
    logger.info(f"   Headers: {websocket.headers}")
    
    try:
        await websocket.accept()
        logger.info(f"✅ Camera WebSocket accepted: {client_id}")
        
        first_message = await websocket.receive_json()
        logger.info(f"📦 Received registration: {first_message}")
        
        # Handle the client
        await image_receiver.handle_client_with_id(websocket, client_id, first_message)
        
    except WebSocketDisconnect:
        logger.info(f"Camera client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        import traceback
        logger.error(traceback.format_exc())


# ==================== SHARED UPLOAD LOGIC ====================
async def handle_image_upload(
    file: bytes,
    x_client_id: str,
    x_position: str,
    x_photo_number: str,
    x_timestamp: str
):
    """Shared upload logic for both endpoint paths"""
    try:
        client_id = x_client_id or "unknown_camera"
        position = x_position or "unknown"
        photo_num = x_photo_number or "0"
        
        logger.info(f"📷 Received image from {client_id}: position={position}, photo={photo_num}, size={len(file)} bytes")
        
        # Convert to PIL Image
        image = Image.open(BytesIO(file))
        logger.info(f"📸 Image decoded: {image.size[0]}x{image.size[1]} {image.mode}")
        
        # Run YOLO inference
        if yolo_model is not None:
            results = yolo_model([image])
            detections = parse_yolo_results(results)
            
            logger.info(f"✅ Inference complete: {len(detections)} detections")
            
            # Send detections to chatbot
            for detection in detections:
                label = detection['class_name']
                confidence = detection['confidence']
                
                if should_send_detection(label):
                    logger.info(f"� ESP32 Camera detected: {label} ({confidence:.2f})")
                    await send_detection_to_chatbot(label, confidence, client_id)
            
            return JSONResponse({
                "status": "success",
                "client_id": client_id,
                "position": position,
                "photo_number": photo_num,
                "detections": detections,
                "image_size": f"{image.size[0]}x{image.size[1]}"
            })
        else:
            logger.warning("⚠️ YOLO model not initialized")
            return JSONResponse({
                "status": "accepted",
                "message": "Image received but inference not available",
                "client_id": client_id,
                "position": position
            })
            
    except Exception as e:
        logger.error(f"❌ Error processing upload: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/vision/upload")
async def upload_image_with_prefix(
    file: bytes = File(...),
    x_client_id: str = Header(None),
    x_position: str = Header(None),
    x_photo_number: str = Header(None),
    x_timestamp: str = Header(None)
):
    """HTTP endpoint: /vision/upload (full path preserved)"""
    logger.info("🔍 Request at /vision/upload")
    return await handle_image_upload(file, x_client_id, x_position, x_photo_number, x_timestamp)


@app.post("/upload")
async def upload_image_no_prefix(
    file: bytes = File(...),
    x_client_id: str = Header(None),
    x_position: str = Header(None),
    x_photo_number: str = Header(None),
    x_timestamp: str = Header(None)
):
    """HTTP endpoint: /upload (if Tailscale strips /vision)"""
    logger.info("🔍 Request at /upload")
    return await handle_image_upload(file, x_client_id, x_position, x_photo_number, x_timestamp)


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


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with service information"""
    
    # Build detection summary
    if stream_detections:
        detection_items = "".join([
            f'<li><strong>� {d["class_name"]}</strong> - {d["confidence"]:.1%} '
            f'<span style="font-size:0.85em;color:#666;">({d["timestamp"].split("T")[1][:8]})</span></li>'
            for d in stream_detections[:10]
        ])
        detection_summary = f"<ul>{detection_items}</ul>"
    else:
        detection_summary = '<p style="color:#999;font-style:italic;">No animals detected yet</p>'
    
    # Status indicators
    model_status = "✅ Loaded" if yolo_model else "❌ Not Loaded"
    stream_status = "🟢 Active" if inference_active else "🔴 Stopped"
    status_color = "#d4edda" if yolo_model else "#fff3cd"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Zoo Animal Detection</title>
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
            .animal-grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
                margin: 20px 0;
                background: #f7fafc;
                padding: 20px;
                border-radius: 12px;
            }}
            .animal-card {{
                background: white;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                font-size: 0.9em;
                border: 2px solid #e2e8f0;
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
        </style>
    </head>
    <body>
        <div class="container">
            <h1>� Zoo Animal Detection</h1>
            <p class="subtitle">Real-time YOLO-based animal detection system</p>
            
            <div class="status-grid">
                <div class="status-item">
                    <span class="status-label">🤖 Model</span>
                    <span class="status-value">{model_status}</span>
                </div>
                <div class="status-item">
                    <span class="status-label">📹 RTSP Stream</span>
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
            
            <div class="section">
                <h2>🦁 Detectable Animals</h2>
                <div class="animal-grid">
                    <div class="animal-card">🦊 Arctic Fox</div>
                    <div class="animal-card">🦫 Capybara</div>
                    <div class="animal-card">🦭 Harbor Seal</div>
                    <div class="animal-card">🼠Panda</div>
                    <div class="animal-card">🦜 Parrot</div>
                    <div class="animal-card">🧠Penguin</div>
                    <div class="animal-card">🦊 Red Panda</div>
                    <div class="animal-card">🦥 Sloth</div>
                </div>
            </div>
            
            <div class="section detections">
                <h2>🔍 Latest Detections</h2>
                {detection_summary}
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
        'rtsp_stream_active': inference_active,
        'frames_processed': frame_count,
        'chatbot_url': CHATBOT_URL,
        'camera_url': CAMERA_STREAM_URL,
        'animal_classes': ANIMAL_CLASSES
    }


@app.get("/api/detections")
async def get_stream_detections():
    """Get latest detections from camera stream"""
    return {
        'detections': stream_detections,
        'frame_count': frame_count,
        'timestamp': datetime.now().isoformat(),
        'model_loaded': yolo_model is not None,
        'stream_active': inference_active
    }


@app.get("/debug")
async def debug_info():
    """Detailed debug information"""
    
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
        "service": "Zoo Animal Detection Service",
        "timestamp": datetime.now().isoformat(),
        "model": {
            "loaded": yolo_model is not None,
            "path": YOLO_MODEL_PATH,
            "classes": ANIMAL_CLASSES
        },
        "rtsp_stream": {
            "url": CAMERA_STREAM_URL,
            "active": inference_active,
            "frames_processed": frame_count
        },
        "chatbot": {
            "url": CHATBOT_URL,
            "status": chatbot_status,
            "recent_detections_sent": list(last_sent_detections.keys())
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
    logger.info("🚀 Starting Zoo Animal Detection Service")
    uvicorn.run(app, host="0.0.0.0", port=5000)