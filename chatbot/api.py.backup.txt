# api_streaming.py - Updated API with streaming text generation and real-time TTS
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from audio_receiver import AudioReceiver
import asyncio
import json
import os
import base64
import time  
import logging
import re
from typing import Dict, Optional

# Clean logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Import your existing components
from main import HybridMuseumAI  
from config import load_azure_openai_config
from audio_receiver import AudioReceiver
# from streaming_openai import StreamingOpenAI

openai_config = load_azure_openai_config()
assistant = HybridMuseumAI(openai_api_key=openai_config.api_key)
# streaming_ai = StreamingOpenAI()  # New streaming component

# Initialize voice component
try:
    from optimized_voice import OptimizedVoiceComponent
    voice_component = OptimizedVoiceComponent({
        "audio_settings": {"sample_rate": 16000, "channels": 1}
    })
    logger.info("Voice component initialized for streaming")
except Exception as e:
    logger.error(f"Voice component initialization failed: {e}")
    voice_component = None

# Initialize audio receiver for RPi
audio_receiver = AudioReceiver(voice_component) if voice_component else None

# Store active TTS WebSocket connections
tts_connections: Dict[str, WebSocket] = {}

# Store latest CV detection
latest_cv_detection = {"label": None, "timestamp": None, "user_id": None}

# Short fallback responses for kids
SHORT_FALLBACKS = {
    "greet": "Hi there! I'm Artie, your art buddy! What's your name?",
    "van_gogh": "Van Gogh's cafe painting shows a French cafe under the brilliant stars! Want to see it?",
    "lady_jane": "Lady Jane Grey's story is really dramatic! It's like a movie in a painting. Should we find it?",
    "traquair": "The Victory painting is super detailed and colorful! It tells an amazing adventure story.",
    "hours": "We're open Tuesday to Sunday, 10 AM to 5 PM! Best time is morning!",
    "kids": "We have awesome art stations and treasure hunts! What sounds fun to you?",
    "default": "Our museum has amazing art! What would you like to explore?"
}
# Define stream_response_to_tts_client function BEFORE using it
async def stream_response_to_tts_client(response_text: str, websocket: WebSocket, client_id: str):
    """Stream response sentence by sentence to TTS client"""
    logger.info(f"Streaming response to {client_id}: {response_text[:50]}...")
    
    # Split into sentences
    sentences = re.split(r'[.!?]+', response_text)
    sentence_count = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_count += 1
        sentence_text = sentence + ("!" if sentence_count == 1 else ".")
        
        logger.info(f"Sending sentence {sentence_count} to {client_id}: {sentence_text}")
        
        # Send to TTS client (RPi will play with espeak)
        await websocket.send_json({
            "type": "stream_chunk",
            "text": sentence_text,
            "sentence_number": sentence_count,
            "is_complete": False
        })

        # Small pause between sentences
        await asyncio.sleep(0.2)
    
    # Send completion signal
    await websocket.send_json({
        "type": "stream_complete",
        "total_sentences": sentence_count,
        "is_complete": True
    })

    logger.info(f"Response streaming complete for {client_id}")

# NOW initialize audio_receiver (after tts_connections and stream_func are defined)
audio_receiver = AudioReceiver(
    voice_component,
    assistant=assistant,
    tts_connections=tts_connections,
    stream_func=stream_response_to_tts_client
) if voice_component else None

# ADD this function to your api.py file (after the imports, before the websocket handler):

async def stream_single_response(response_text: str, websocket: WebSocket):
    """Stream a complete response sentence by sentence with TTS"""
    logger.info(f"Streaming database-enhanced response: {response_text[:50]}...")
    
    # Split into sentences
    sentences = re.split(r'[.!?]+', response_text)
    sentence_count = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        sentence_count += 1
        # Add appropriate punctuation
        if sentence_count == 1:
            sentence_text = sentence + "!"
        else:
            sentence_text = sentence + "."
        
        logger.info(f"Sending database sentence {sentence_count}: {sentence_text}")
        
        # Generate TTS if available
        audio_base64 = None
        if voice_component and voice_component.tts_available:
            try:
                audio_data = await asyncio.wait_for(
                    voice_component.create_audio_response_async(sentence_text),
                    timeout=5.0
                )
                if audio_data:
                    audio_base64 = base64.b64encode(audio_data).decode()
                    logger.info(f"TTS generated for database sentence {sentence_count}")
            except Exception as e:
                logger.warning(f"TTS error for sentence {sentence_count}: {e}")
        
        # Send streaming chunk
        await websocket.send_json({
            "type": "stream_chunk",
            "text": sentence_text,
            "audio": audio_base64,
            "sentence_number": sentence_count,
            "is_complete": False,
            "source": "database_enhanced"  # Mark as database-sourced
        })
        
        # Small pause between sentences
        await asyncio.sleep(0.3)
    
    # Send completion signal
    await websocket.send_json({
        "type": "stream_complete",
        "total_sentences": sentence_count,
        "is_complete": True,
        "source": "database_enhanced"
    })
    
def get_short_fallback(message: str) -> str:
    """Get short fallback response"""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["hello", "hi", "hey"]):
        return SHORT_FALLBACKS["greet"]
    elif "van gogh" in message_lower:
        return SHORT_FALLBACKS["van_gogh"]
    elif "lady jane" in message_lower or "jane grey" in message_lower:
        return SHORT_FALLBACKS["lady_jane"]
    elif "traquair" in message_lower or "victory" in message_lower:
        return SHORT_FALLBACKS["traquair"]
    elif "hours" in message_lower or "open" in message_lower:
        return SHORT_FALLBACKS["hours"]
    elif "kids" in message_lower or "activities" in message_lower:
        return SHORT_FALLBACKS["kids"]
    else:
        return SHORT_FALLBACKS["default"]

async def sentence_by_sentence_tts(text_stream, websocket):
    """Generate TTS as soon as we have complete sentences"""
    current_sentence = ""
    sentence_count = 0
    
    async for chunk in text_stream:
        current_sentence += chunk
        
        # Check for sentence endings
        if re.search(r'[.!?]\s*$', current_sentence.strip()):
            sentence_count += 1
            sentence_text = current_sentence.strip()
            
            logger.info(f"Sentence {sentence_count} complete: '{sentence_text}'")
            
            # Generate TTS for this sentence
            if voice_component and voice_component.tts_available and sentence_text:
                try:
                    audio_data = await asyncio.wait_for(
                        voice_component.create_audio_response_async(sentence_text),
                        timeout=5.0
                    )
                    
                    if audio_data:
                        audio_base64 = base64.b64encode(audio_data).decode()
                        
                        # Send streaming chunk with audio
                        await websocket.send_json({
                            "type": "stream_chunk",
                            "text": sentence_text,
                            "audio": audio_base64,
                            "sentence_number": sentence_count,
                            "is_complete": False
                        })
                        
                        logger.info(f"Sent sentence {sentence_count} with TTS")
                    else:
                        # Send text only if TTS fails
                        await websocket.send_json({
                            "type": "stream_chunk", 
                            "text": sentence_text,
                            "audio": None,
                            "sentence_number": sentence_count,
                            "is_complete": False
                        })
                        
                except asyncio.TimeoutError:
                    logger.warning(f"TTS timeout for sentence {sentence_count}")
                    # Send without audio
                    await websocket.send_json({
                        "type": "stream_chunk",
                        "text": sentence_text,
                        "audio": None,
                        "sentence_number": sentence_count,
                        "is_complete": False
                    })
                    
                except Exception as e:
                    logger.error(f"TTS error for sentence {sentence_count}: {e}")
                    # Send without audio
                    await websocket.send_json({
                        "type": "stream_chunk",
                        "text": sentence_text,
                        "audio": None,
                        "sentence_number": sentence_count,
                        "is_complete": False
                    })
            else:
                # Send text only if no TTS
                await websocket.send_json({
                    "type": "stream_chunk",
                    "text": sentence_text,
                    "audio": None,
                    "sentence_number": sentence_count,
                    "is_complete": False
                })
            
            # Reset for next sentence
            current_sentence = ""
    
    # Handle any remaining text that didn't end with punctuation
    if current_sentence.strip():
        sentence_count += 1
        await websocket.send_json({
            "type": "stream_chunk",
            "text": current_sentence.strip(),
            "audio": None,
            "sentence_number": sentence_count,
            "is_complete": False
        })
    
    # Send completion signal
    await websocket.send_json({
        "type": "stream_complete",
        "total_sentences": sentence_count,
        "is_complete": True
    })

@app.get("/")
async def root():
    """Serve the main page"""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading page: {str(e)}</h1>")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """UPDATED: Streaming WebSocket endpoint"""
    await websocket.accept()
    
    user_id = f"user_{hash(str(websocket.client))}_{int(time.time())}"[-10:]
    logger.info(f"WebSocket connected for user: {user_id}")
    
    # Send quick welcome message
    try:
        welcome_message = "Hi! I'm Artie, your museum buddy! What's your name?"
        
        # Quick welcome TTS
        welcome_audio = None
        if voice_component and voice_component.tts_available:
            try:
                welcome_audio_data = await asyncio.wait_for(
                    voice_component.create_audio_response_async(welcome_message),
                    timeout=3.0
                )
                if welcome_audio_data:
                    welcome_audio = base64.b64encode(welcome_audio_data).decode()
            except Exception as e:
                logger.warning(f"Welcome TTS error: {e}")
        
        await websocket.send_json({
            "type": "welcome",
            "text": welcome_message,
            "audio": welcome_audio,
            "streaming_enabled": True
        })
        
    except Exception as e:
        logger.error(f"Welcome error: {e}")
    
    # Main message handling loop
    while True:
        try:
            data = await websocket.receive_json()

            if data["type"] == "text":
                message = data["message"]
                logger.info(f"Processing: '{message[:30]}...' for user: {user_id}")
                
                start_time = time.time()
                
                try:
                    # Get latest CV detection for this user
                    cv_context = None
                    if latest_cv_detection["label"] and latest_cv_detection["timestamp"]:
                        if time.time() - latest_cv_detection["timestamp"] < 30:
                            cv_context = latest_cv_detection["label"]
                            logger.info(f"Using CV context: {cv_context}")
                    
                    # Pass CV context to assistant
                    full_response = await assistant.process_message(
                        message, 
                        user_id,
                        cv_detected_artifact=cv_context  # NEW: Pass CV detection
                    )

                    await stream_single_response(full_response, websocket)
                    
                except Exception as e:
                    logger.error(f"Assistant error: {e}")
                    # Fallback to short static response
                    fallback_response = get_short_fallback(message)
                    await stream_single_response(fallback_response, websocket)
                    
                    total_time = time.time() - start_time
                    logger.info(f"Message processed in {total_time:.2f}s total")
                    
                except Exception as e:
                    logger.error(f"Processing error: {e}")
                    fallback = get_short_fallback(message)
                    await websocket.send_json({
                        "type": "error",
                        "message": fallback
                    })

            elif data["type"] == "audio":
                # Handle audio input (existing logic, but with shorter responses)
                try:
                    audio_data = base64.b64decode(data["audio"])
                    logger.info(f"Processing audio: {len(audio_data)} bytes")
                    
                    recognized_text = ""
                    if voice_component:
                        try:
                            recognized_text = await asyncio.wait_for(
                                voice_component.process_audio_to_text_async(audio_data),
                                timeout=10.0
                            )
                        except Exception as e:
                            logger.error(f"Speech recognition error: {e}")
                    
                    if recognized_text and recognized_text.strip():
                        # Process recognized text with streaming
                        context = {
                            'query_type': 'general_art',
                            'detected_artifact': assistant._detect_artifact(recognized_text)
                        }

                        # USE FULL ASSISTANT PIPELINE for audio too
                        try:
                            logger.info("Using full assistant pipeline for audio...")
                            full_response = await assistant.process_message(recognized_text, user_id)
                            await stream_single_response(full_response, websocket)
                        except Exception as e:
                            logger.error(f"Audio assistant error: {e}")
                            fallback_response = get_short_fallback(recognized_text)
                            await stream_single_response(fallback_response, websocket)                        

                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Could not understand audio. Please try again!"
                        })
                        
                except Exception as e:
                    logger.error(f"Audio processing error: {e}")
                    await websocket.send_json({
                        "type": "error", 
                        "message": "Audio processing failed. Please try text!"
                    })
                
        except Exception as e:
            logger.error(f"WebSocket Error: {str(e)}")
            break

# New WebSocket endpoint for RPi audio input
# Replace the /ws/audio endpoint in api.py with this:

@app.websocket("/ws/audio")
async def audio_websocket(websocket: WebSocket):
    """WebSocket endpoint for Raspberry Pi audio streaming"""
    await websocket.accept()
    
    # Generate temporary ID
    temp_id = f"rpi_{hash(str(websocket.client))}_{int(time.time())}"[-10:]
    client_id = temp_id  # Will be updated from registration
    
    logger.info(f"🎤 Audio WebSocket connected (temp): {temp_id}")
    
    if not audio_receiver:
        await websocket.send_json({
            "type": "error",
            "message": "Audio receiver not available"
        })
        await websocket.close()
        return
    
    try:
        # Wait for registration to get real client_id
        first_message = await websocket.receive_json()
        
        if first_message.get("type") == "register":
            # Use the client_id from registration
            client_id = first_message.get("client_id", temp_id)
            logger.info(f"✅ Audio client registered with ID: {client_id}")
            
            # Send back to audio_receiver for full handling
            # Create a modified handle_client that uses this client_id
            await audio_receiver.handle_client_with_id(websocket, client_id, first_message)
        else:
            # If first message is not registration, use temp_id
            logger.warning(f"⚠️ First message was not registration, using temp ID")
            await audio_receiver.handle_client(websocket, temp_id)
            
    except Exception as e:
        logger.error(f"Audio WebSocket error: {e}")
    finally:
        logger.info(f"🎤 Audio WebSocket disconnected: {client_id}")
        
# New WebSocket endpoint for RPi TTS output
@app.websocket("/ws/tts")
async def tts_websocket(websocket: WebSocket):
    """WebSocket endpoint for streaming text responses to RPi TTS client"""
    await websocket.accept()
    
    try:
        # Receive registration
        data = await websocket.receive_json()
        client_id = data.get("client_id", f"tts_{int(time.time())}")
        
        logger.info(f"TTS client connected: {client_id}")
        
        # Store connection for routing responses
        tts_connections[client_id] = websocket

        # Send confirmation
        await websocket.send_json({
            "type": "connected",
            "message": "TTS client registered",
            "client_id": client_id
        })

        # Store this connection for routing responses
        # (You'll need to implement routing logic based on your needs)
        
        # Keep connection alive and listen for commands
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=60.0
                )

                # Handle different message types from RPi
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
                elif message.get("type") == "text_query":
                    # RPi sends text query -> process with OpenAI -> stream back
                    query = message.get("text", "")
                    logger.info(f"Processing text query from {client_id}: {query}")
                    
                    # Process with assistant
                    try:
                        response = await assistant.process_message(query, client_id)
                        
                        # Stream response back sentence by sentence
                        await stream_response_to_tts_client(response, websocket, client_id)
                        
                    except Exception as e:
                        logger.error(f"Query processing error: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "message": str(e)
                        })

            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"type": "keepalive"})
            
    except Exception as e:
        logger.error(f"TTS WebSocket error: {e}")
    finally:
        if client_id in tts_connections:
            del tts_connections[client_id]
        logger.info(f"🔊 TTS client disconnected: {client_id}")

async def stream_response_to_tts_client(response_text: str, websocket: WebSocket, client_id: str):
    """Stream response sentence by sentence to TTS client"""
    logger.info(f"Streaming response to {client_id}: {response_text[:50]}...")
    
    # Split into sentences
    sentences = re.split(r'[.!?]+', response_text)
    sentence_count = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_count += 1
        sentence_text = sentence + ("!" if sentence_count == 1 else ".")
        
        logger.info(f"Sending sentence {sentence_count} to {client_id}: {sentence_text}")
        
        # Send to TTS client (RPi will play with espeak)
        await websocket.send_json({
            "type": "stream_chunk",
            "text": sentence_text,
            "sentence_number": sentence_count,
            "is_complete": False
        })

        # Small pause between sentences
        await asyncio.sleep(0.2)
    
    # Send completion signal
    await websocket.send_json({
        "type": "stream_complete",
        "total_sentences": sentence_count,
        "is_complete": True
    })

    logger.info(f"Response streaming complete for {client_id}")

@app.websocket("/ws/rpi")
async def rpi_integrated_websocket(websocket: WebSocket):
    """Single WebSocket for complete RPi audio -> text -> response -> TTS flow"""
    await websocket.accept()
    
    client_id = f"rpi_{hash(str(websocket.client))}_{int(time.time())}"[-10:]
    logger.info(f"🤖 Integrated RPi client connected: {client_id}")
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            # Handle audio streaming
            if msg_type == "audio_chunk":
                # Process audio (delegate to audio_receiver logic)
                audio_base64 = data.get("audio")
                audio_bytes = base64.b64decode(audio_base64)
                
                # For simplicity, accumulate and process on complete
                # (You can make this streaming like audio_receiver.py)
                
            elif msg_type == "audio_complete":
                # Process complete audio -> STT
                logger.info("Processing complete audio for STT...")
                # (Implement STT logic here)
                
            elif msg_type == "text_query":
                # Direct text query -> OpenAI -> TTS
                query = data.get("text", "")
                logger.info(f"Text query from {client_id}: {query}")
                
                try:
                    # Get response from assistant
                    response = await assistant.process_message(query, client_id)
                    
                    # Stream back to RPi
                    await stream_response_to_tts_client(response, websocket, client_id)
                    
                except Exception as e:
                    logger.error(f"Processing error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
                    
    except Exception as e:
        logger.error(f"Integrated WebSocket error: {e}")
    finally:
        logger.info(f"🤖 Integrated RPi client disconnected: {client_id}")

@app.get("/health")
async def health_check():
    """Health check with streaming status"""
    return {
        "status": "healthy",
        "streaming_enabled": True,
        "voice_available": voice_component is not None,
        "tts_available": voice_component.tts_available if voice_component else False,
        "openai_available": True,
        "sentence_by_sentence_tts": True,
        "max_response_length": "100 tokens (very short)",
        "estimated_response_time": "< 1 second first sentence"
    }

@app.get("/test-database")
async def test_database():
    """Test if custom database is being used"""
    try:
        import sqlite3
        import os
        
        # Check if database exists
        db_paths_to_check = [
            'museum.db',
            'muznc1/museum.db', 
            './muznc1/museum.db',
            os.path.join(os.path.dirname(__file__), 'museum.db'),
            os.path.join(os.path.dirname(__file__), 'muznc1', 'museum.db')
        ]
        
        database_info = {
            "database_found": False,
            "database_path": None,
            "artworks_count": 0,
            "sample_artworks": [],
            "assistant_database_path": None,
            "assistant_search_test": None
        }
        
        # Find the database
        for db_path in db_paths_to_check:
            if os.path.exists(db_path):
                database_info["database_found"] = True
                database_info["database_path"] = db_path
                logger.info(f"Found database at: {db_path}")
                break
        
        if database_info["database_found"]:
            # Connect and get sample data
            conn = sqlite3.connect(database_info["database_path"])
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM artifacts")
            database_info["artworks_count"] = cursor.fetchone()[0]
            
            # Get sample artworks
            cursor.execute("SELECT title, artist, description FROM artifacts LIMIT 3")
            results = cursor.fetchall()
            
            for title, artist, description in results:
                database_info["sample_artworks"].append({
                    "title": title or "Unknown",
                    "artist": artist or "Unknown", 
                    "description": (description or "No description available")[:100] + "..."
                })
            
            conn.close()
        
        # Check what the assistant is actually using
        try:
            if hasattr(assistant, 'db_path'):
                database_info["assistant_database_path"] = assistant.db_path
            elif hasattr(assistant, 'enhanced_rag') and hasattr(assistant.enhanced_rag, 'db_path'):
                database_info["assistant_database_path"] = assistant.enhanced_rag.db_path
            
            # Test the assistant's database search
            if hasattr(assistant, 'enhanced_rag'):
                test_result = assistant.enhanced_rag.enhanced_artwork_search("Van Gogh", "cafe terrace")
                if test_result:
                    database_info["assistant_search_works"] = True
                    database_info["test_search_result"] = {
                        "title": test_result[0] or "Unknown",
                        "artist": test_result[1] or "Unknown"
                    }
                else:
                    database_info["assistant_search_works"] = False
                    
                # Test context building
                context = assistant._get_relevant_local_context("Tell me about Van Gogh")
                database_info["context_sample"] = context[:200] + "..." if context else "No context"
                
        except Exception as e:
            database_info["assistant_error"] = str(e)
        
        return database_info
        
    except Exception as e:
        return {
            "error": str(e),
            "database_found": False
        }

from fastapi import Body
from typing import Optional

# Store latest CV detection (simple in-memory approach)
latest_cv_detection = {"label": None, "timestamp": None, "user_id": None}

@app.post("/cv/detection")
async def receive_cv_detection(
    label: str = Body(...),
    user_id: str = Body(...),
    confidence: Optional[float] = Body(None)
):
    """Receive CV detection results from the CV container"""
    global latest_cv_detection
    
    latest_cv_detection = {
        "label": label,
        "timestamp": time.time(),
        "user_id": user_id,
        "confidence": confidence
    }
    
    logger.info(f"CV detected: {label} for user {user_id} (confidence: {confidence})")
    
    return {"status": "received", "label": label}

@app.get("/cv/latest/{user_id}")
async def get_latest_detection(user_id: str):
    """Get the latest CV detection for a user"""
    if latest_cv_detection["user_id"] == "default_user" or latest_cv_detection["user_id"] == user_id:        # Check if detection is recent (within last 30 seconds)
        if time.time() - latest_cv_detection["timestamp"] < 30:
            return latest_cv_detection
    
    return {"label": None, "message": "No recent detection"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Museum AI Assistant with RPi Integration")
    logger.info("Endpoints:")
    logger.info("  - /ws/audio : RPi audio streaming")
    logger.info("  - /ws/tts : RPi TTS client")
    logger.info("  - /ws/rpi : Integrated RPi endpoint")
    logger.info("  - /ws : Browser clients")
    uvicorn.run(app, host="0.0.0.0", port=8000)