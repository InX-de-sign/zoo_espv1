# audio_receiver.py - MINIMAL FIX: Only add CV context storage
import asyncio
import json
import base64
import logging
import wave
import io
import time
from typing import Optional, Dict
from starlette.websockets import WebSocketDisconnect
from collections import deque
from esp32_tts_streamer import ESP32TTSStreamer
from pydub import AudioSegment
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioReceiver:
    """Receives audio from clients and streams TTS responses"""
    
    def __init__(self, voice_component, assistant=None, tts_connections=None, stream_func=None, recent_detections=None, stt_component=None):
        self.voice_component = voice_component  # TTS component
        self.stt_component = stt_component or voice_component  # STT component (defaults to voice_component for backward compatibility)
        self.assistant = assistant
        self.tts_connections = tts_connections
        self.stream_func = stream_func
        self.recent_detections = recent_detections
        
        self.esp32_streamer = ESP32TTSStreamer(voice_component)
        
        self.audio_queues: Dict[str, deque] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        self.client_settings: Dict[str, dict] = {}
        
        # 🆕 ONLY NEW ADDITION: Store CV context per client
        self.client_cv_context: Dict[str, Optional[str]] = {}
        
        if not voice_component:
            logger.error("❌ Voice component required!")
        else:
            logger.info("✅ Audio receiver initialized with ESP32 support")

    def _get_cv_context(self, client_id: str) -> Optional[str]:
        """Get recent CV detection for this client"""
        # 🆕 First check stored context
        if client_id in self.client_cv_context:
            stored_animal = self.client_cv_context[client_id]
            if stored_animal:
                logger.info(f"🎯 Using stored CV context for {client_id}: {stored_animal}")
                return stored_animal
        
        # Fallback to recent detections
        if not self.recent_detections:
            return None
            
        detection = self.recent_detections.get(client_id)
        
        if detection:
            detected_at = detection.get("detected_at")
            if detected_at:
                age_seconds = (datetime.now() - detected_at).total_seconds()
                if age_seconds < 120:  # Within 2 minutes
                    animal = detection.get("animal")
                    logger.info(f"🎯 CV context for {client_id}: {animal} (detected {age_seconds:.0f}s ago)")
                    # 🆕 Store it for this session
                    self.client_cv_context[client_id] = animal
                    return animal
        
        return None    

    async def handle_text_query(self, text: str, client_id: str, websocket):
        """Handle direct text query (for testing or button-based input)"""
        logger.info(f"📝 Text query from {client_id}: '{text}'")
        
        try:
            await websocket.send_json({
                "type": "text_processing",
                "message": "Processing your question..."
            })
            
            await websocket.send_json({
                "type": "stt_result",
                "text": text,
                "client_id": client_id
            })

            cv_detected_animal = self._get_cv_context(client_id)
            
            await self._process_with_openai_and_stream(text, client_id, websocket, cv_detected_animal)              
            logger.info("✅ Text query processed successfully")
            
        except Exception as e:
            logger.error(f"❌ Text query error: {e}", exc_info=True)
            await websocket.send_json({
                "type": "error",
                "message": f"Text processing failed: {str(e)}"
            })

    async def handle_client_with_id(
        self, 
        websocket, 
        client_id: str, 
        first_message: Dict,
        cv_detected_animal: str = None
    ):
        """Handle ESP32 audio client"""
        logger.info(f"🎤 Handling audio for client: {client_id}")
        
        if cv_detected_animal:
            self.client_cv_context[client_id] = cv_detected_animal
            logger.info(f"🎯 Session CV context set: {cv_detected_animal}")
        
        try:
            message_type = first_message.get("type")
            
            if message_type == "register":
                logger.info(f"📝 ESP32 {client_id} registered")
                
                await websocket.send_json({
                    "type": "register_ack",
                    "message": "Registration successful",
                    "client_id": client_id
                })
                
                if client_id not in self.audio_queues:
                    self.audio_queues[client_id] = deque(maxlen=100)
                
                if client_id not in self.processing_tasks or self.processing_tasks[client_id].done():
                    self.processing_tasks[client_id] = asyncio.create_task(
                        self._process_audio_queue(client_id, websocket)
                    )
                    logger.info(f"🔄 Started audio processing task for {client_id}")
                
                await self._handle_audio_stream(client_id, websocket)
                return
            
            elif message_type == "text_query":
                text = first_message.get("text", "")
                if text:
                    await self.handle_text_query(text, client_id, websocket)
                return
            
            elif message_type == "settings":
                self.client_settings[client_id] = {
                    "sample_rate": first_message.get("sample_rate", 44100),
                    "channels": first_message.get("channels", 1),
                    "bits": first_message.get("bits", 16)
                }
                logger.info(f"📊 Stored settings for {client_id}: {self.client_settings[client_id]}")
                
                await websocket.send_json({
                    "type": "settings_ack",
                    "message": "Settings received"
                })
                
                await self._handle_audio_stream(client_id, websocket)
                
            elif message_type == "audio_chunk":
                logger.info(f"🎵 First message is audio chunk, starting stream handler")
                
                if client_id not in self.audio_queues:
                    self.audio_queues[client_id] = deque(maxlen=100)
                
                if client_id not in self.client_settings:
                    self.client_settings[client_id] = {
                        "sample_rate": first_message.get("sample_rate", 44100),
                        "channels": first_message.get("channels", 1),
                        "bits": 16
                    }
                
                # Decode first audio chunk
                audio_data_b64 = first_message.get("audio")
                if audio_data_b64:
                    try:
                        audio_bytes = base64.b64decode(audio_data_b64)
                        self.audio_queues[client_id].append(audio_bytes)
                        logger.info(f"📥 Queued first audio chunk: {len(audio_bytes)} bytes")
                    except Exception as e:
                        logger.error(f"❌ Failed to decode first audio chunk: {e}")
                
                if client_id not in self.processing_tasks or self.processing_tasks[client_id].done():
                    self.processing_tasks[client_id] = asyncio.create_task(
                        self._process_audio_queue(client_id, websocket)
                    )
                    logger.info(f"🔄 Started audio processing task for {client_id}")
                
                await self._handle_audio_stream(client_id, websocket)
            
            else:
                logger.warning(f"⚠️ Unknown message type: {message_type}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
                
             
        except Exception as e:
            logger.error(f"❌ Audio handler error: {e}", exc_info=True)
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
            except:
                pass
        finally:
            # ✅ Cancel processing task
            if client_id in self.processing_tasks:
                task = self.processing_tasks[client_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                del self.processing_tasks[client_id]
                logger.info(f"🧹 Cancelled processing task for {client_id}")
            
            # ✅ Clear queue
            if client_id in self.audio_queues:
                del self.audio_queues[client_id]
                logger.info(f"🧹 Cleared audio queue for {client_id}")
            
            if client_id in self.client_cv_context:
                del self.client_cv_context[client_id]
                logger.info(f"🧹 Cleared CV context for {client_id}")

    async def _handle_audio_stream(self, client_id: str, websocket):
        """Handle incoming audio stream - KEEP ORIGINAL PROTOCOL"""
        logger.info(f"🎧 Audio stream handler for {client_id}")
        
        try:
            while True:
                try:
                    message = await websocket.receive_json()
                except WebSocketDisconnect:
                    logger.info(f"Client {client_id} disconnected")
                    break
                
                msg_type = message.get("type")
                logger.info(f"📨 Received message type: {msg_type} from {client_id}")  # 🆕 Added logging
                
                if msg_type == "audio_chunk":
                    # ORIGINAL PROTOCOL: audio field contains base64
                    audio_data_b64 = message.get("audio")
                    
                    if audio_data_b64:
                        try:
                            audio_bytes = base64.b64decode(audio_data_b64)
                            
                            if client_id not in self.audio_queues:
                                self.audio_queues[client_id] = deque(maxlen=100)
                            
                            self.audio_queues[client_id].append(audio_bytes)
                            logger.info(f"📥 Queued audio chunk: {len(audio_bytes)} bytes (total chunks: {len(self.audio_queues[client_id])})")  # 🆕 Changed to info
                            
                        except Exception as e:
                            logger.error(f"❌ Decode error: {e}")
                    else:
                        logger.warning(f"⚠️ audio_chunk message has no 'audio' field")  # 🆕 Added warning
                
                elif msg_type == "audio_complete":
                    logger.info(f"🎵 Audio complete signal from {client_id}")
                    
                    if client_id in self.audio_queues:
                        chunks_count = len([x for x in self.audio_queues[client_id] if isinstance(x, bytes)])
                        logger.info(f"✅ Queued complete signal ({chunks_count} audio chunks received)")  # 🆕 Show chunk count
                        self.audio_queues[client_id].append("COMPLETE")
                    else:
                        logger.warning(f"⚠️ Received complete signal but no audio queue for {client_id}")  # 🆕 Added warning
                
                elif msg_type == "settings":
                    self.client_settings[client_id] = {
                        "sample_rate": message.get("sample_rate", 44100),
                        "channels": message.get("channels", 1),
                        "bits": message.get("bits", 16)
                    }
                    logger.info(f"📊 Updated settings for {client_id}")
                
                else:
                    logger.warning(f"⚠️ Unknown message type: {msg_type} - Full message: {message}")  # 🆕 Changed to warning with full message
                    
        except Exception as e:
            logger.error(f"❌ Stream error: {e}", exc_info=True)
        finally:
            logger.info(f"🧹 Stream cleanup for {client_id}")
                                                        
    async def _process_audio_queue(self, client_id: str, websocket):
        """⚡ OPTIMIZED: Process audio chunks → STT → OpenAI → TTS → Stream
        Now with early processing - starts STT as soon as first chunk arrives!"""
        audio_chunks = []
        first_chunk_received = False
        
        logger.info(f"🔄 Audio processing task STARTED for {client_id}")

        while True:
            try:
                if client_id not in self.audio_queues:
                    logger.warning(f"⚠️ Queue disappeared for {client_id}")
                    break
                
                if not self.audio_queues[client_id]:
                    await asyncio.sleep(0.05)
                    continue
                
                item = self.audio_queues[client_id].popleft()
                
                # ⚡ OPTIMIZATION: Track first chunk for early processing
                if isinstance(item, bytes) and not first_chunk_received:
                    first_chunk_received = True
                    logger.info(f"🚀 First audio chunk received - preparing for STT")
                    try:
                        await websocket.send_json({
                            "type": "audio_receiving",
                            "message": "Listening..."
                        })
                    except:
                        pass

                if item == "COMPLETE":
                    if len(audio_chunks) > 0:
                        logger.info(f"🎯 Processing {len(audio_chunks)} chunks")
                        
                        # ✅ Check websocket state before sending
                        try:
                            await websocket.send_json({
                                "type": "stt_processing",
                                "message": "Processing speech..."
                            })
                        except Exception as e:
                            logger.warning(f"⚠️ Websocket closed, cannot send status: {e}")
                            audio_chunks = []
                            continue
                        
                        if len(audio_chunks) == 1:
                            combined_wav = audio_chunks[0]
                            logger.info(f"📦 Single chunk: {len(combined_wav)} bytes")
                        else:
                            combined_wav = self._combine_to_proper_wav(audio_chunks, client_id)
                            if combined_wav:
                                logger.info(f"🔧 Combined {len(audio_chunks)} chunks: {len(combined_wav)} bytes")
                            else:
                                logger.error(f"❌ Failed to combine {len(audio_chunks)} chunks")

                        if combined_wav:
                            logger.info(f"🎙️ Starting STT on {len(combined_wav)} bytes...")
                            text = await self._google_stt(combined_wav)
                            
                            if text and text.strip():
                                logger.info(f"✅ STT Result: '{text}'")
                                
                                # ✅ Check websocket state
                                try:
                                    await websocket.send_json({
                                        "type": "stt_result",
                                        "text": text,
                                        "client_id": client_id
                                    })
                                except Exception as e:
                                    logger.warning(f"⚠️ Cannot send STT result, websocket closed: {e}")
                                    audio_chunks = []
                                    continue
                                
                                cv_detected_animal = self._get_cv_context(client_id)

                                await self._process_with_openai_and_stream(text, client_id, websocket, cv_detected_animal)
                            else:
                                logger.warning("⚠️ Empty STT result")
                                try:
                                    await websocket.send_json({
                                        "type": "stt_result",
                                        "text": "",
                                        "error": "No speech detected"
                                    })
                                except:
                                    pass
                        else:
                            logger.error("❌ Failed to get valid audio data")
                    
                        audio_chunks = []
                    else:
                        logger.warning("⚠️ COMPLETE signal but no chunks!")
                    continue
                
                if isinstance(item, bytes):
                    audio_chunks.append(item)
                    logger.debug(f"📥 Added chunk {len(audio_chunks)}, size: {len(item)} bytes")
                else:
                    logger.warning(f"⚠️ Skipping non-bytes item: {type(item)}")
            
            except asyncio.CancelledError:
                logger.info(f"Processing cancelled for {client_id}")
                break
            except Exception as e:
                logger.error(f"❌ Processing error: {e}", exc_info=True)
                await asyncio.sleep(0.1)
                            
    async def _process_with_openai_and_stream(self, text: str, client_id: str, websocket, cv_detected_animal: Optional[str] = None):        
        """Process with OpenAI and stream TTS responses with parallel MP3 generation"""
        if not self.assistant:
            logger.warning("⚠️ Assistant not configured")
            return
        
        try:
            # 🆕 Log CV context if present
            if cv_detected_animal:
                logger.info(f"🎯 Processing with CV context: {cv_detected_animal}")
            
            logger.info(f"🤖 Processing with OpenAI: '{text}'")
            
            await websocket.send_json({
                "type": "openai_processing",
                "message": "Getting AI response..."
            })

            word_buffer = ""
            MIN_WORDS = 8
            MAX_WORDS = 20
            
            # ⚡ Queue for parallel TTS generation
            tts_tasks = []
            phrase_count = 0
                        
            # Stream and generate TTS in parallel as phrases arrive
            async for text_chunk in self.assistant.stream_message(text, client_id, cv_detected_animal):
                word_buffer += text_chunk
                current_words = len(word_buffer.split())
                
                has_strong_ending = any(punct in word_buffer for punct in ['.', '!', '?'])
                
                # Start TTS generation immediately when we have a complete phrase
                if has_strong_ending and current_words >= MIN_WORDS:
                    phrase = word_buffer.strip()
                    if phrase and len(phrase) > 5:
                        phrase_count += 1
                        logger.info(f"📝 Phrase {phrase_count}: {phrase[:50]}...")
                        # ⚡ Start generating MP3 immediately in parallel
                        task = asyncio.create_task(self._generate_and_queue_mp3(phrase, phrase_count))
                        tts_tasks.append(task)
                    word_buffer = ""
                    
                elif current_words >= MAX_WORDS:
                    best_break = -1
                    for punct in ['.', '!', '?', ',']:
                        pos = word_buffer.rfind(punct)
                        if pos > len(word_buffer) // 2:
                            best_break = pos
                            break
                    
                    if best_break > 0:
                        phrase = word_buffer[:best_break + 1].strip()
                        if phrase and len(phrase) > 5:
                            phrase_count += 1
                            logger.info(f"📝 Phrase {phrase_count}: {phrase[:50]}...")
                            # ⚡ Start generating MP3 immediately in parallel
                            task = asyncio.create_task(self._generate_and_queue_mp3(phrase, phrase_count))
                            tts_tasks.append(task)
                        word_buffer = word_buffer[best_break + 1:].strip()
            
            # Handle remaining text
            if word_buffer.strip() and len(word_buffer.strip()) > 5:
                phrase_count += 1
                logger.info(f"📝 Final phrase {phrase_count}: {word_buffer.strip()[:50]}...")
                task = asyncio.create_task(self._generate_and_queue_mp3(word_buffer.strip(), phrase_count))
                tts_tasks.append(task)
            
            logger.info(f"✅ Collected {phrase_count} phrases, waiting for TTS generation...")
            
            # Wait for all MP3 generation to complete
            mp3_results = await asyncio.gather(*tts_tasks, return_exceptions=True)
            
            # Stream MP3s in order
            for idx, result in enumerate(mp3_results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Phrase {idx+1} TTS failed: {result}")
                    continue
                
                if not isinstance(result, tuple):
                    logger.error(f"❌ Phrase {idx+1} returned invalid result")
                    continue
                    
                phrase_num, mp3_audio = result
                
                if not mp3_audio or len(mp3_audio) < 100:
                    logger.error(f"❌ Phrase {phrase_num} TTS produced empty audio")
                    continue
                
                try:
                    # Convert MP3 to WAV for ESP32 I2S
                    logger.info(f"📤 [{phrase_num}/{phrase_count}] Converting and streaming {len(mp3_audio)} bytes MP3→WAV")
                    
                    from pydub import AudioSegment
                    import io
                    
                    # Convert MP3 to WAV
                    audio = AudioSegment.from_mp3(io.BytesIO(mp3_audio))
                    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                    
                    wav_buffer = io.BytesIO()
                    audio.export(wav_buffer, format="wav")
                    wav_bytes = wav_buffer.getvalue()
                    
                    logger.info(f"✅ Converted to WAV: {len(wav_bytes)} bytes")
                    
                    chunk_size = 4096
                    await websocket.send_json({
                        "type": "audio_start",
                        "format": "wav",
                        "total_bytes": len(wav_bytes),
                        "phrase": phrase_num,
                        "total_phrases": phrase_count
                    })
                    
                    # Stream WAV chunks
                    for i in range(0, len(wav_bytes), chunk_size):
                        chunk = wav_bytes[i:i + chunk_size]
                        await websocket.send_bytes(chunk)
                        await asyncio.sleep(0.001)
                    
                    await websocket.send_json({
                        "type": "audio_complete",
                        "phrase": phrase_num
                    })
                    
                    logger.info(f"✅ [{phrase_num}/{phrase_count}] Streamed")
                    
                except Exception as e:
                    logger.error(f"❌ Phrase {phrase_num} streaming error: {e}")

            logger.info(f"✅ All phrases streamed")
                        
        except Exception as e:
            logger.error(f"❌ OpenAI error: {e}", exc_info=True)
    
    async def _generate_and_queue_mp3(self, phrase: str, phrase_num: int) -> tuple:
        """Generate MP3 for a phrase (runs in parallel)"""
        try:
            logger.info(f"🎵 [{phrase_num}] Starting TTS generation...")
            mp3_audio = await self.voice_component.create_audio_response_async(phrase)
            logger.info(f"✅ [{phrase_num}] TTS complete: {len(mp3_audio) if mp3_audio else 0} bytes")
            return (phrase_num, mp3_audio)
        except Exception as e:
            logger.error(f"❌ [{phrase_num}] TTS error: {e}")
            return (phrase_num, None)
    
    async def _stream_single_phrase_mp3(self, phrase: str, idx: int, total: int, websocket, client_id: str):
        """⚡ Stream a single phrase with MP3→WAV conversion for ESP32 I2S speaker"""
        try:
            logger.info(f"🎵 [{idx+1}/{total}] Starting WAV stream: {phrase[:50]}...")
            
            # ✅ Use WAV streaming method - converts MP3→WAV for I2S compatibility!
            await self.esp32_streamer.stream_response_to_esp32(phrase, websocket, client_id)
            
            logger.info(f"✅ [{idx+1}/{total}] Phrase streamed")
            
        except Exception as e:
            logger.error(f"❌ [{idx+1}/{total}] Streaming error: {e}")
                
    def _combine_to_proper_wav(self, chunks: list, client_id: str) -> Optional[bytes]:
        """Combine audio chunks - handles mixed WAV/raw format"""
        try:
            settings = self.client_settings.get(client_id, {})
            sample_rate = settings.get("sample_rate", 16000)
            channels = settings.get("channels", 1)
            
            if not chunks:
                logger.error("❌ No chunks to combine")
                return None
            
            all_audio_data = []
            
            # Process each chunk individually
            for i, chunk in enumerate(chunks):
                try:
                    # Check if this chunk has WAV header
                    if len(chunk) > 44 and chunk[0:4] == b'RIFF':
                        # Extract audio data from WAV
                        chunk_io = io.BytesIO(chunk)
                        with wave.open(chunk_io, 'rb') as wf:
                            audio_frames = wf.readframes(wf.getnframes())
                            all_audio_data.append(audio_frames)
                            logger.debug(f"  Chunk {i}: WAV extracted {len(audio_frames)} bytes")
                    else:
                        # Raw audio data
                        all_audio_data.append(chunk)
                        logger.debug(f"  Chunk {i}: Raw {len(chunk)} bytes")
                except Exception as e:
                    logger.warning(f"  Chunk {i} error: {e}")
                    continue
            
            if not all_audio_data:
                logger.error("❌ No valid audio extracted")
                return None
            
            combined_audio_data = b''.join(all_audio_data)
            logger.info(f"✅ Combined {len(chunks)} chunks → {len(combined_audio_data)} bytes")
            
            # Create final WAV file
            output_buffer = io.BytesIO()
            with wave.open(output_buffer, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(combined_audio_data)
            
            result = output_buffer.getvalue()
            logger.info(f"✅ Final WAV: {len(result)} bytes")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Combining error: {e}", exc_info=True)
            return None
                                
    async def _google_stt(self, audio_bytes: bytes) -> Optional[str]:
        """Google Speech Recognition"""
        if not self.stt_component:
            return None
        
        if len(audio_bytes) < 10000:
            logger.warning(f"⚠️ Audio too short: {len(audio_bytes)} bytes")
            return None
        
        try:
            logger.info(f"🎙️ Running Google STT on {len(audio_bytes)} bytes...")
            
            text = await asyncio.wait_for(
                self.stt_component.process_audio_to_text_async(
                    audio_bytes,
                    "audio/wav"
                ),
                timeout=30.0
            )
            
            if text and text.strip():
                logger.info(f"✅ STT success: '{text}'")
                return text.strip()
            else:
                logger.warning("⚠️ STT returned empty")
                return None
            
        except asyncio.TimeoutError:
            logger.error("❌ STT timeout")
            return None
        except Exception as e:
            logger.error(f"❌ STT error: {e}", exc_info=True)
            return None