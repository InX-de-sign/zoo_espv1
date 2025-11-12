# cv/mock_cv_service.py - Simplified mock CV for YOLO integration
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import asyncio
import random
import time
import logging
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock Museum CV Service", version="1.0.0")

# Three specific artifacts in your museum
MUSEUM_ARTIFACTS = [
    {
        "label": "Cafe Terrace at Night",
        "artist": "Vincent van Gogh",
        "keywords": ["van gogh", "cafe", "terrace", "night", "stars"]
    },
    {
        "label": "Lady Jane Grey",
        "artist": "Paul Delaroche", 
        "keywords": ["lady jane", "jane grey", "execution", "delaroche"]
    },
    {
        "label": "The Progress of the Soul - Victory",
        "artist": "Phoebe Anna Traquair",
        "keywords": ["traquair", "victory", "embroidery", "scottish"]
    }
]

# Configuration
CHATBOT_URL = "http://chatbot:8000"  # Docker network address
AUTO_DETECTION_INTERVAL = 60  # 1 minute
auto_detection_active = False

async def send_detection_to_chatbot(label: str, user_id: str, confidence: float):
    """Send CV detection to chatbot API"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{CHATBOT_URL}/cv/detection",
                json={
                    "label": label,
                    "user_id": user_id,
                    "confidence": confidence
                }
            )
            logger.info(f"Sent detection to chatbot: {label} -> {response.status_code}")
            return response.json()
    except Exception as e:
        logger.error(f"Failed to send to chatbot: {e}")
        return None

async def auto_detection_loop():
    """Simulate continuous artifact detection every minute"""
    global auto_detection_active
    auto_detection_active = True
    
    logger.info("🎨 AUTO-DETECTION: Started (1 detection per minute)")
    
    while auto_detection_active:
        try:
            # FIXED: Randomly select an artifact for proper testing
            artifact = random.choice(MUSEUM_ARTIFACTS)
            confidence = random.uniform(0.85, 0.98)
            
            user_id = "default_user"
            
            logger.info(f"🔍 AUTO-DETECTED: {artifact['label']} (confidence: {confidence:.2f})")
            
            # Send to chatbot
            result = await send_detection_to_chatbot(
                label=artifact['label'],
                user_id=user_id,
                confidence=confidence
            )
            
            if result:
                logger.info(f"✅ Detection sent successfully")
            
        except Exception as e:
            logger.error(f"Auto-detection error: {e}")
        
        # Wait before next detection
        await asyncio.sleep(AUTO_DETECTION_INTERVAL)

@app.on_event("startup")
async def startup_event():
    """Start auto-detection when service starts"""
    asyncio.create_task(auto_detection_loop())
    logger.info("Mock CV Service started with auto-detection enabled")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop auto-detection on shutdown"""
    global auto_detection_active
    auto_detection_active = False
    logger.info("Auto-detection stopped")

# FIXED: Random artifact selection, not always Van Gogh
@app.get("/detect-current")
async def detect_current_painting():
    """Detect what painting is currently in view - returns random artifact for testing"""
    await asyncio.sleep(random.uniform(0.5, 1.0))  # Simulate processing time
    
    # FIXED: Select random artifact instead of always Van Gogh
    artifact = random.choice(MUSEUM_ARTIFACTS)
    confidence = random.uniform(0.88, 0.96)
    
    detection = {
        "label": artifact['label'],
        "artist": artifact['artist'],
        "confidence": round(confidence, 3),
        "bounding_box": {
            "x": random.randint(80, 150),
            "y": random.randint(40, 100), 
            "width": random.randint(350, 500),
            "height": random.randint(450, 700)
        },
        "detection_time": round(random.uniform(0.8, 1.5), 2)
    }
    
    logger.info(f"Current detection: {detection['label']} (confidence: {detection['confidence']})")
    
    return JSONResponse(content={
        "status": "found",
        "detection": detection,
        "message": "Detected painting in view",
        "timestamp": time.time()
    })

@app.get("/current")
async def get_current():
    """Alias for detect-current"""
    return await detect_current_painting()

@app.get("/detect")
async def detect():
    """Another alias for detect-current"""
    return await detect_current_painting()

# REMOVED: File upload analyze endpoint - not needed for YOLO integration
# In your real YOLO system, this would be replaced by your YOLO detection code
# that processes camera feed and sends artifact labels directly to the chatbot

@app.post("/yolo_detection")
async def yolo_detection(label: str, confidence: float = 0.9, user_id: str = "default_user"):
    """
    Endpoint for your real YOLO system to send detection results
    This replaces the file upload approach
    
    Your YOLO code should call this endpoint like:
    POST /yolo_detection?label=Van%20Gogh%20-%20Cafe%20Terrace%20at%20Night&confidence=0.92
    """
    try:
        # Validate confidence
        if not 0.0 <= confidence <= 1.0:
            raise HTTPException(status_code=400, detail="Confidence must be between 0.0 and 1.0")
        
        # Send to chatbot
        result = await send_detection_to_chatbot(
            label=label,
            user_id=user_id,
            confidence=confidence
        )
        
        logger.info(f"YOLO detection: {label} (confidence: {confidence:.3f}) -> sent to chatbot")
        
        return JSONResponse(content={
            "status": "success",
            "label": label,
            "confidence": confidence,
            "user_id": user_id,
            "sent_to_chatbot": True,
            "chatbot_response": result,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"YOLO detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/manual_detect")
async def manual_detection(user_id: str = "default_user", artifact_index: int = None):
    """Manually trigger a detection (for testing)"""
    try:
        if artifact_index is not None and 0 <= artifact_index < len(MUSEUM_ARTIFACTS):
            artifact = MUSEUM_ARTIFACTS[artifact_index]
        else:
            artifact = random.choice(MUSEUM_ARTIFACTS)
        
        confidence = random.uniform(0.85, 0.98)
        
        result = await send_detection_to_chatbot(
            label=artifact['label'],
            user_id=user_id,
            confidence=confidence
        )
        
        return {
            "status": "detection_sent",
            "artifact": artifact['label'],
            "user_id": user_id,
            "confidence": confidence,
            "chatbot_response": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """Check auto-detection status"""
    return {
        "auto_detection_active": auto_detection_active,
        "interval_seconds": AUTO_DETECTION_INTERVAL,
        "artifacts_count": len(MUSEUM_ARTIFACTS),
        "artifacts": [a['label'] for a in MUSEUM_ARTIFACTS],
        "chatbot_url": CHATBOT_URL
    }

@app.post("/control/start")
async def start_detection():
    """Manually start auto-detection"""
    global auto_detection_active
    if not auto_detection_active:
        asyncio.create_task(auto_detection_loop())
        return {"status": "started", "message": "Auto-detection activated"}
    return {"status": "already_running"}

@app.post("/control/stop")
async def stop_detection():
    """Manually stop auto-detection"""
    global auto_detection_active
    auto_detection_active = False
    return {"status": "stopped", "message": "Auto-detection deactivated"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "mock-cv",
        "auto_detection": auto_detection_active,
        "chatbot_url": CHATBOT_URL,
        "artifacts": len(MUSEUM_ARTIFACTS),
        "endpoints": [
            "/detect-current",
            "/current", 
            "/detect",
            "/yolo_detection",
            "/manual_detect",
            "/status",
            "/health"
        ]
    }

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Museum CV Mock Service",
        "version": "1.0.0",
        "status": "running",
        "auto_detection": auto_detection_active,
        "artifacts": len(MUSEUM_ARTIFACTS),
        "description": "Mock CV service for museum YOLO integration",
        "integration_notes": {
            "for_yolo": "Use POST /yolo_detection to send detection results",
            "for_testing": "Use GET /detect-current for random detections",
            "for_manual": "Use POST /manual_detect for specific artifacts"
        },
        "available_endpoints": {
            "GET /": "This information",
            "GET /health": "Health check",
            "GET /status": "Detection status",
            "GET /detect-current": "Get random painting detection",
            "POST /yolo_detection": "Send YOLO detection results to chatbot",
            "POST /manual_detect": "Manually trigger detection",
            "POST /control/start": "Start auto-detection",
            "POST /control/stop": "Stop auto-detection"
        }
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Mock CV Service for YOLO Integration")
    uvicorn.run(app, host="0.0.0.0", port=8001)