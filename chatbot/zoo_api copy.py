# zoo_api.py - FastAPI for Zoo chatbot with ESP32 support (Tailscale Funnel compatible)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from datetime import datetime 
import asyncio
import json
import os
import logging

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

# Initialize components
openai_config = load_azure_openai_config()
assistant = HybridZooAI(openai_api_key=openai_config.api_key, db_path="zoo.db")
voice_component = OptimizedVoiceComponent()

# Initialize audio receiver with ESP32 support
audio_receiver = AudioReceiver(
    voice_component=voice_component,
    assistant=assistant
)

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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for web-based real-time chat"""
    await websocket.accept()
    
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
                response = await assistant.process_message(message, client_id)
                
                await websocket.send_json({
                    "type": "response",
                    "message": response
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
    🆕 ESP32 Audio WebSocket - COMPLETE WORKFLOW
    
    This endpoint handles:
    1. Receives audio chunks from ESP32
    2. Transcribes with Google STT
    3. Processes with OpenAI
    4. Generates Google TTS
    5. Converts to ESP32 format (16kHz WAV)
    6. Streams audio back to ESP32
    
    Protocol:
    - ESP32 sends: {"type": "register", "audio_settings": {...}}
    - ESP32 sends: {"type": "audio_chunk", "audio": "base64...", "chunk_id": 0}
    - ESP32 sends: {"type": "audio_complete", "total_chunks": 100}
    - Server sends: {"type": "stt_result", "text": "..."}
    - Server sends: {"type": "tts_start", "total_bytes": 50000, ...}
    - Server sends: binary audio chunks
    - Server sends: {"type": "tts_complete", "total_bytes": 50000}
    """
    await websocket.accept()
    logger.info(f"🎤 ESP32 audio client connected: {client_id}")
    
    keepalive_task = asyncio.create_task(
        send_keepalive_pings(websocket, client_id)
    )

    try:
        # Wait for registration
        first_message = await websocket.receive_json()
        
        # Handle with audio receiver (supports complete workflow)
        await audio_receiver.handle_client_with_id(websocket, client_id, first_message)
        
    except WebSocketDisconnect:
        logger.info(f"🔌 ESP32 disconnected: {client_id}")
    except Exception as e:
        logger.error(f"❌ ESP32 error: {e}", exc_info=True)
    finally:
        # ✅ Cancel keepalive task
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