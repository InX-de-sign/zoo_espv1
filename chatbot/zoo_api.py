# zoo_api.py - FastAPI for Zoo chatbot with ESP32 support (Tailscale Funnel compatible)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import Dict, Any
from datetime import datetime 
import asyncio
import json
import os
import logging

DEFAULT_CAMERA_ID = "esp32_robot_camera" 

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ocean Park Zoo Chatbot API")

# Import components
from zoo_main import HybridZooAI
from config import load_azure_openai_config
from optimized_voice import OptimizedVoiceComponent
from audio_receiver import AudioReceiver

# Store recent detections for each user
recent_detections: Dict[str, Dict[str, Any]] = {}

# Initialize components
openai_config = load_azure_openai_config()
assistant = HybridZooAI(openai_api_key=openai_config.api_key, db_path="zoo.db")
voice_component = OptimizedVoiceComponent()

# Initialize audio receiver with ESP32 support
audio_receiver = AudioReceiver(
    voice_component=voice_component,
    assistant=assistant,
    recent_detections=recent_detections 
)

# Map camera IDs to audio client IDs
CLIENT_ID_MAPPING = {
    "esp32_robot_camera": "esp32_1",
    "esp32_1": "esp32_1"
}

def get_mapped_id(client_id: str) -> str:
    """Get the canonical ID for a client"""
    return CLIENT_ID_MAPPING.get(client_id, client_id)

# Mount static files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Serve the chatbot interface"""
    html_path = os.path.join("static", "zoo_index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="""
        <html>
            <head><title>Ocean Park Zoo Chatbot</title></head>
            <body>
                <h1>🐼 Ocean Park Zoo Chatbot</h1>
                <h2>WebSocket Endpoints:</h2>
                <ul>
                    <li><strong>Web Chat:</strong> /ws</li>
                    <li><strong>ESP32 Audio:</strong> /ws/esp32/audio/{client_id}</li>
                    <li><strong>RPi Audio (legacy):</strong> /ws/audio/{client_id}</li>
                </ul>
                <p><strong>Access via Tailscale Funnel:</strong> https://inx-fiona.tail4fb9a3.ts.net</p>
                <p><em>WebSocket connections will use wss:// (secure) automatically when accessed via HTTPS</em></p>
            </body>
        </html>
        """)

# Add this to zoo_api.py after the @app.get("/") endpoint

from fastapi import Request

@app.post("/cv/detection")
async def receive_cv_detection(request: Request):
    """
    Receive animal detection from YOLO inference service
    
    Expected JSON:
    {
        "label": "capybara",
        "user_id": "esp32_robot_camera", 
        "confidence": 0.95
    }
    """
    try:
        data = await request.json()
        label = data.get("label")
        user_id = data.get("user_id", "default_user")
        confidence = data.get("confidence", 0.0)
        
        # 🎯 MAP THE ID to canonical client_id
        mapped_id = get_mapped_id(user_id)
        
        logger.info(f"🎯 CV Detection received: {label} ({confidence:.2f}) for user {user_id}")
        if mapped_id != user_id:
            logger.info(f"   📍 Mapped {user_id} → {mapped_id}")
        
        # Store detection with MAPPED ID
        recent_detections[mapped_id] = {
            "animal": label,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
            "detected_at": datetime.now()
        }
        
        greeting = f"Oh wow! I see you're looking at a {label}! "
        
        if label == "capybara":
            greeting += "Capybaras are the world's largest rodents - they're like giant, chill hamsters!"
        elif label == "panda":
            greeting += "Giant pandas spend up to 14 hours a day eating bamboo!"
        elif label == "red-panda":
            greeting += "Red pandas are actually more related to raccoons than giant pandas!"
        elif label == "sloth":
            greeting += "Sloths move so slowly that algae grows on their fur!"
        elif label == "penguin":
            greeting += "Penguins can swim up to 22 miles per hour underwater!"
        elif label == "arctic-fox":
            greeting += "Arctic foxes have the warmest fur of any mammal!"
        elif label == "harbor-seal":
            greeting += "Harbor seals can hold their breath for up to 30 minutes!"
        elif label == "parrot":
            greeting += "Some parrots can live over 80 years!"
        
        logger.info(f"✅ Detection stored for {mapped_id}: {label}")
        
        return {
            "status": "received",
            "label": label,
            "user_id": user_id,
            "mapped_id": mapped_id,
            "confidence": confidence,
            "auto_greeting": greeting
        }
        
    except Exception as e:
        logger.error(f"❌ Error receiving CV detection: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/cv/recent/{user_id}")
async def get_recent_detection(user_id: str):
    """Get the most recent CV detection for a user"""
    detection = recent_detections.get(user_id)
    
    if detection:
        # Check if detection is recent (within last 2 minutes)
        detected_at = detection.get("detected_at")
        if detected_at:
            age_seconds = (datetime.now() - detected_at).total_seconds()
            if age_seconds < 120:  # 2 minutes
                return {
                    "status": "found",
                    "detection": detection,
                    "age_seconds": age_seconds
                }
    
    return {
        "status": "no_recent_detection",
        "user_id": user_id
    }


@app.get("/cv/detections")
async def list_all_detections():
    """List all recent detections across all users"""
    return {
        "total_users": len(recent_detections),
        "detections": recent_detections
    }

# Replace the websocket endpoint in zoo_api.py with this enhanced version

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for web-based real-time chat WITH CV CONTEXT"""
    await websocket.accept()  # ✅ Accept FIRST
    
    client_id = f"web_{hash(str(websocket.client))}_{int(asyncio.get_event_loop().time())}"[-10:]
    logger.info(f"🐼 Web client connected: {client_id}")
    
    try:
        await websocket.send_json({
            "type": "system",
            "message": "Welcome to Ocean Park! I'm your zoo guide!"
        })
        
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            
            if not message:
                continue
            
            logger.info(f"Query from {client_id}: {message}")
            
            await websocket.send_json({
                "type": "thinking",
                "message": "Let me check..."
            })
            
            try:
                # 🎯 CHECK FOR RECENT CV DETECTION
                # Use the DEFAULT_CAMERA_ID since web clients don't have their own camera
                cv_detected_animal = None
                if DEFAULT_CAMERA_ID in recent_detections:
                    detection = recent_detections[DEFAULT_CAMERA_ID]
                    detected_at = detection.get("detected_at")
                    
                    if detected_at:
                        age_seconds = (datetime.now() - detected_at).total_seconds()
                        if age_seconds < 120:  # Detection within last 2 minutes
                            cv_detected_animal = detection.get("animal")
                            logger.info(f"🎯 Using CV context: {cv_detected_animal} (detected {age_seconds:.0f}s ago)")
                
                # Process with CV context
                response = await assistant.process_message(
                    message, 
                    client_id,
                    cv_detected_animal=cv_detected_animal  # Pass CV detection
                )
                
                await websocket.send_json({
                    "type": "response",
                    "message": response,
                    "cv_detected": cv_detected_animal  # Include in response
                })
                
            except Exception as e:
                logger.error(f"Processing error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Sorry, I had trouble with that question."
                })
    
    except WebSocketDisconnect:
        logger.info(f"Web client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

@app.websocket("/ws/esp32/audio/{client_id}")
async def esp32_audio_endpoint(websocket: WebSocket, client_id: str):
    """
    🆕 ESP32 Audio WebSocket WITH CV CONTEXT
    
    Now includes animal detection context when processing queries
    """
    await websocket.accept()
    logger.info(f"🎤 ESP32 audio client connected: {client_id}")
    
    keepalive_task = asyncio.create_task(
        send_keepalive_pings(websocket, client_id)
    )

    try:
        first_message = await websocket.receive_json()
        
        # 🎯 CHECK FOR RECENT CV DETECTION BEFORE PROCESSING
        cv_detected_animal = None
        if client_id in recent_detections:
            detection = recent_detections[client_id]
            detected_at = detection.get("detected_at")
            
            if detected_at:
                age_seconds = (datetime.now() - detected_at).total_seconds()
                if age_seconds < 120:  # Detection within last 2 minutes
                    cv_detected_animal = detection.get("animal")
                    logger.info(f"🎯 ESP32 using CV context: {cv_detected_animal} (detected {age_seconds:.0f}s ago)")
        
        # Pass CV context to audio receiver
        await audio_receiver.handle_client_with_id(
            websocket, 
            client_id, 
            first_message,
            cv_detected_animal=cv_detected_animal  # ✅ PASS CV CONTEXT
        )
        
    except WebSocketDisconnect:
        logger.info(f"🔌 ESP32 disconnected: {client_id}")
    except Exception as e:
        logger.error(f"❌ ESP32 error: {e}", exc_info=True)
    finally:
        keepalive_task.cancel()
        try:
            await keepalive_task
        except asyncio.CancelledError:
            pass

async def send_keepalive_pings(websocket: WebSocket, client_id: str):
    """Send periodic pings to keep connection alive"""
    try:
        while True:
            await asyncio.sleep(20)  # Ping every 20 seconds
            try:
                await websocket.send_json({
                    "type": "keepalive",
                    "timestamp": datetime.now().isoformat()
                })
                logger.debug(f"📡 Sent keepalive to {client_id}")
            except Exception as e:
                logger.debug(f"Keepalive failed for {client_id}: {e}")
                break
    except asyncio.CancelledError:
        logger.debug(f"Keepalive task cancelled for {client_id}")



@app.websocket("/ws/audio/{client_id}")
async def rpi_audio_endpoint(websocket: WebSocket, client_id: str):
    """Legacy endpoint for Raspberry Pi clients"""
    await websocket.accept()
    logger.info(f"🎤 RPi audio client connected: {client_id}")
    
    try:
        first_message = await websocket.receive_json()
        await audio_receiver.handle_client_with_id(websocket, client_id, first_message)
        
    except WebSocketDisconnect:
        logger.info(f"🔌 RPi disconnected: {client_id}")
    except Exception as e:
        logger.error(f"❌ RPi error: {e}", exc_info=True)
        

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Ocean Park Zoo Chatbot",
        "port": 8000,
        "endpoints": {
            "web_chat": "/ws",
            "esp32_audio": "/ws/esp32/audio/{client_id}",
            "rpi_audio": "/ws/audio/{client_id}"
        },
        "access": {
            "tailscale_funnel": "https://inx-fiona.tail4fb9a3.ts.net",
            "local": "http://localhost:8000"
        },
        "components": {
            "openai": True,
            "google_tts": voice_component.tts_available,
            "google_stt": voice_component.recognizer is not None,
            "database": os.path.exists(assistant.db_path) if hasattr(assistant, 'db_path') else False
        }
    }

@app.get("/test-tts")
async def test_tts():
    """Test if TTS actually works"""
    try:
        test_text = "Hello! This is a test."
        logger.info(f"Testing TTS with text: '{test_text}'")
        
        audio = await voice_component.create_audio_response_async(test_text)
        
        result = {
            "tts_available": voice_component.tts_available,
            "gtts_available": voice_component.gtts_available,
            "pygame_available": voice_component.pygame_available,
            "audio_generated": audio is not None,
            "audio_size": len(audio) if audio else 0,
            "test_text": test_text
        }
        
        logger.info(f"TTS Test Result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"TTS Test Error: {e}", exc_info=True)
        return {"error": str(e)}

@app.get("/test-audio")
async def test_audio():
    """Test audio components"""
    try:
        # Test TTS
        test_text = "Hello! This is a test of the Google TTS system."
        audio = await voice_component.create_audio_response_async(test_text)
        
        return {
            "status": "success",
            "tts_available": voice_component.tts_available,
            "stt_available": voice_component.recognizer is not None,
            "test_audio_size": len(audio) if audio else 0,
            "message": "Audio components working" if audio else "TTS failed"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/test-database")
async def test_database():
    """Test if zoo database is working"""
    try:
        import sqlite3
        
        if not assistant.db_path or not os.path.exists(assistant.db_path):
            return {"error": "Database not found", "path": assistant.db_path}
        
        conn = sqlite3.connect(assistant.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM animals")
        count = cursor.fetchone()[0]
        
        cursor.execute("SELECT common_name, scientific_name, location_at_park FROM animals LIMIT 5")
        samples = cursor.fetchall()
        
        conn.close()
        
        return {
            "status": "success",
            "database_path": assistant.db_path,
            "total_animals": count,
            "sample_animals": [
                {"name": name, "scientific": sci, "location": loc}
                for name, sci, loc in samples
            ]
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/animals")
async def list_animals():
    """List all animals in database"""
    try:
        import sqlite3
        
        if not assistant.db_path or not os.path.exists(assistant.db_path):
            return {"error": "Database not found"}
        
        conn = sqlite3.connect(assistant.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT common_name, scientific_name, habitat, location_at_park
            FROM animals
            ORDER BY common_name
        ''')
        
        animals = cursor.fetchall()
        conn.close()
        
        return {
            "total": len(animals),
            "animals": [
                {
                    "name": name,
                    "scientific_name": sci,
                    "habitat": habitat,
                    "location": location
                }
                for name, sci, habitat, location in animals
            ]
        }
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    logger.info("=" * 60)
    logger.info("🐼 Starting Ocean Park Zoo Chatbot API")
    logger.info("=" * 60)
    logger.info("Port: 8000")
    logger.info("Local: http://localhost:8000")
    logger.info("Tailscale Funnel: https://inx-fiona.tail4fb9a3.ts.net")
    logger.info("Web Chat: /ws (wss:// via HTTPS)")
    logger.info("ESP32 Audio: /ws/esp32/audio/{client_id}")
    logger.info("Health: /health")
    logger.info("=" * 60)
    
    # Create database if needed
    if not os.path.exists("zoo.db"):
        logger.info("Creating zoo database...")
        from create_zoo_database import create_zoo_database
        create_zoo_database()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)