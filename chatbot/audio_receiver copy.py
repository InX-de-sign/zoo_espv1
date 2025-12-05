# audio_receiver.py - UPDATED FOR ESP32 with TTS streaming
import asyncio
import json
import base64
import logging
import wave
import io
from typing import Optional, Dict
from fastapi import WebSocket
from collections import deque
from esp32_tts_streamer import ESP32TTSStreamer
from pydub import AudioSegment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioReceiver:
    """Receives audio from clients and streams TTS responses"""
    
    def __init__(self, voice_component, assistant=None, tts_connections=None, stream_func=None):
        self.voice_component = voice_component
        self.assistant = assistant
        self.tts_connections = tts_connections
        self.stream_func = stream_func
        
        # NEW: ESP32 TTS Streamer
        self.esp32_streamer = ESP32TTSStreamer(voice_component)
        
        self.audio_queues: Dict[str, deque] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        self.client_settings: Dict[str, dict] = {}
        
        if not voice_component:
            logger.error("❌ Voice component required!")
        else:
            logger.info("✅ Audio receiver initialized with ESP32 support")

    async def handle_text_query(self, text: str, client_id: str, websocket: WebSocket):
        """Handle direct text query (for testing or button-based input)"""
        logger.info(f"📝 Text query from {client_id}: '{text}'")
        
        try:
            # Send processing notification
            await websocket.send_json({
                "type": "text_processing",
                "message": "Processing your question..."
            })
            
            # Send STT result (even though it's text input)
            await websocket.send_json({
                "type": "stt_result",
                "text": text,
                "client_id": client_id
            })
            
            # Process with OpenAI and stream audio response
            await self._process_with_openai_and_stream(text, client_id, websocket)
            
            logger.info("✅ Text query processed successfully")
            
        except Exception as e:
            logger.error(f"❌ Text query error: {e}", exc_info=True)
            await websocket.send_json({
                "type": "error",
                "message": f"Text processing failed: {str(e)}"
            })

    async def handle_client_with_id(self, websocket: WebSocket, client_id: str, first_message: dict):
        """Handle audio from ESP32/RPi client"""
        logger.info(f"🎤 Audio receiver started for client: {client_id}")
        
        # ✅ Clean up old task if it exists (in case of reconnect)
        if client_id in self.processing_tasks:
            logger.info(f"🧹 Cancelling old processing task for {client_id}")
            self.processing_tasks[client_id].cancel()
            try:
                await self.processing_tasks[client_id]
            except asyncio.CancelledError:
                pass
        
        # Initialize queue and task
        self.audio_queues[client_id] = deque(maxlen=300)
        self.processing_tasks[client_id] = asyncio.create_task(
            self._process_audio_queue(client_id, websocket)
        )
        
        logger.info(f"✅ Processing task started for {client_id}")

        audio_reassembly = {}
        
        # Process registration
        if first_message.get("type") == "register":
            self.client_settings[client_id] = first_message.get("audio_settings", {})
            logger.info(f"✅ Registered: {client_id}")
            
            await websocket.send_json({
                "type": "registered",
                "message": "Registered",
                "client_id": client_id
            })
        
        try:
            while True:
                data = await websocket.receive_json()
                
                if data.get("type") == "audio_chunk":
                    audio_base64 = data.get("audio")

                    logger.info(f"📦 Received chunk with audio field: {bool(audio_base64)}, length: {len(audio_base64) if audio_base64 else 0}")

                    if not audio_base64:
                        logger.warning(f"⚠️ Missing audio data in chunk")
                        logger.warning(f"📋 Full message keys: {data.keys()}")
                        continue

                    try:
                        audio_bytes = base64.b64decode(audio_base64)
                        chunk_id = data.get("chunk_id", 0)

                        if chunk_id == 0:
                            # First chunk - reset buffer
                            audio_reassembly[client_id] = []
                            total_size = data.get("total_size", 0)
                            if total_size:
                                logger.info(f"📦 Starting audio reassembly: {total_size} bytes")
                    
                        audio_reassembly.setdefault(client_id, []).append(audio_bytes)
                    
                        if chunk_id % 3 == 0:
                            logger.debug(f"📥 Chunk {chunk_id}: {len(audio_bytes)} bytes")
                    
                    except Exception as e:
                        logger.error(f"❌ Failed to decode audio chunk: {e}")
                        continue
                
                elif data.get("type") == "audio_complete":
                    total_chunks = data.get('total_chunks', 0)
                    logger.info(f"🎤 Audio complete: {total_chunks} chunks")
                    
                    if client_id in audio_reassembly and audio_reassembly[client_id]:
                        combined_audio = b''.join(audio_reassembly[client_id])
                        logger.info(f"✅ Reassembled {len(combined_audio)} bytes from {len(audio_reassembly[client_id])} chunks")

                        if client_id in self.audio_queues:
                            self.audio_queues[client_id].append(combined_audio)
                            self.audio_queues[client_id].append("COMPLETE")

                        del audio_reassembly[client_id]

                elif data.get("type") == "text_query":
                    text = data.get("text", "")
                    if text.strip():
                        await self.handle_text_query(text, client_id, websocket)
                
                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
        except Exception as e:
            logger.error(f"❌ Client error: {e}", exc_info=True)
        finally:
            # Cleanup
            if client_id in self.processing_tasks:
                self.processing_tasks[client_id].cancel()
                try:
                    await self.processing_tasks[client_id]
                except asyncio.CancelledError:
                    pass
                del self.processing_tasks[client_id]
            
            if client_id in self.audio_queues:
                del self.audio_queues[client_id]
            
            if client_id in self.client_settings:
                del self.client_settings[client_id]
            
            logger.info(f"🔌 Disconnected: {client_id}")
    
    async def _process_audio_queue(self, client_id: str, websocket: WebSocket):
        """Process audio chunks → STT → OpenAI → TTS → Stream to ESP32"""
        audio_chunks = []
        
        logger.info(f"🔄 Audio processing task STARTED for {client_id}")  # ← ADD THIS
    
        while True:
            try:
                if client_id not in self.audio_queues:
                    logger.warning(f"⚠️ Queue disappeared for {client_id}")
                    break
                
                if not self.audio_queues[client_id]:
                    await asyncio.sleep(0.05)
                    continue
                
                item = self.audio_queues[client_id].popleft()
                logger.debug(f"📥 Dequeued item: {type(item)} (size: {len(item) if isinstance(item, bytes) else 'N/A'})")

                if item == "COMPLETE":
                    if len(audio_chunks) > 0:
                        logger.info(f"🎯 Processing {len(audio_chunks)} chunks")
                        
                        await websocket.send_json({
                            "type": "stt_processing",
                            "message": "Processing speech..."
                        })
                        
                        if len(audio_chunks) == 1:
                            # Single reassembled audio file
                            combined_wav = audio_chunks[0]
                            logger.info(f"📦 Using reassembled audio: {len(combined_wav)} bytes")
                        else:
                            # Multiple chunks need combining
                            combined_wav = self._combine_to_proper_wav(audio_chunks, client_id)
                            logger.info(f"🔧 Combined multiple chunks: {len(combined_wav)} bytes")
                        
                        if combined_wav:
                            logger.info(f"🎙️ Starting STT on {len(combined_wav)} bytes...")
                            
                            # STT
                            text = await self._google_stt(combined_wav)
                            
                            if text and text.strip():
                                logger.info(f"✅ STT Result: '{text}'")
                                
                                await websocket.send_json({
                                    "type": "stt_result",
                                    "text": text,
                                    "client_id": client_id
                                })
                                
                                # Process with OpenAI and stream audio response
                                await self._process_with_openai_and_stream(text, client_id, websocket)
                            else:
                                logger.warning("⚠️ Empty STT result")
                                await websocket.send_json({
                                    "type": "stt_result",
                                    "text": "",
                                    "error": "No speech detected"
                                })
                        else:
                            logger.error("❌ Failed to get valid audio data")
                    
                        audio_chunks = []
                    

                    else:
                        logger.warning("⚠️ COMPLETE signal received but no audio chunks!")
                    
                        continue
                
                audio_chunks.append(item)
                logger.debug(f"📥 Added audio chunk {len(audio_chunks)}, size: {len(item)} bytes")
            
            except asyncio.CancelledError:
                logger.info(f"Processing cancelled for {client_id}")
                break
            except Exception as e:
                logger.error(f"❌ Processing error: {e}", exc_info=True)
                await asyncio.sleep(0.1)
    
    async def _process_with_openai_and_stream(self, text: str, client_id: str, websocket: WebSocket):
        """
        SEQUENTIAL: Generate and stream one phrase at a time with smart phrase splitting
        """
        if not self.assistant:
            logger.warning("⚠️ Assistant not configured")
            return
        
        try:
            logger.info(f"🤖 Processing with OpenAI (SEQUENTIAL STREAMING): '{text}'")
            
            await websocket.send_json({
                "type": "openai_processing",
                "message": "Getting AI response..."
            })

            phrases = []
            word_buffer = ""
            MIN_WORDS = 5
            MAX_WORDS = 12  # ✅ REDUCED from 20 to 12 for shorter audio chunks
            
            # Step 1: Collect all phrases from OpenAI with SMART splitting
            async for text_chunk in self.assistant.stream_message(text, client_id):
                word_buffer += text_chunk
                current_words = len(word_buffer.split())
                
                # Check for natural sentence endings
                has_ending = any(punct in word_buffer for punct in ['.', '!', '?', ','])  # ✅ Added comma
                
                # Split logic - MORE AGGRESSIVE
                if has_ending and current_words >= MIN_WORDS:
                    # Natural ending with enough words
                    phrase = word_buffer.strip()
                    if phrase:
                        phrases.append(phrase)
                        logger.info(f"📝 Collected phrase {len(phrases)}: {phrase[:50]}...")
                    word_buffer = ""
                    
                elif current_words >= MAX_WORDS:
                    # Too long - find last punctuation or space
                    last_punct = max(
                        word_buffer.rfind(','),
                        word_buffer.rfind(' ')
                    )
                    
                    if last_punct > len(word_buffer) // 2:  # Only split if past halfway
                        phrase = word_buffer[:last_punct].strip()
                        if phrase:
                            phrases.append(phrase)
                            logger.info(f"📝 Collected phrase {len(phrases)}: {phrase[:50]}...")
                        word_buffer = word_buffer[last_punct:].strip()
                    else:
                        # Force split if can't find good break point
                        phrase = word_buffer.strip()
                        if phrase:
                            phrases.append(phrase)
                            logger.info(f"📝 Collected phrase {len(phrases)}: {phrase[:50]}...")
                        word_buffer = ""
            
            # Handle remaining text
            if word_buffer.strip():
                phrases.append(word_buffer.strip())
                logger.info(f"📝 Collected final phrase {len(phrases)}: {word_buffer.strip()[:50]}...")
            
            logger.info(f"✅ Collected {len(phrases)} phrases")
            
            # Filter out very short phrases
            phrases = [p for p in phrases if len(p) > 2]
            logger.info(f"✅ After filtering: {len(phrases)} phrases")
            
            # Step 2: Generate and stream SEQUENTIALLY
            for idx, phrase in enumerate(phrases):
                logger.info(f"🎵 [{idx+1}/{len(phrases)}] Generating TTS: {phrase[:50]}...")
                
                try:
                    mp3_audio = await self.voice_component.create_audio_response_async(phrase)
                    
                    if not mp3_audio or len(mp3_audio) < 100:
                        logger.error(f"❌ [{idx+1}/{len(phrases)}] TTS generation failed")
                        continue
                    
                    logger.info(f"✅ [{idx+1}/{len(phrases)}] Generated {len(mp3_audio)} bytes MP3")
                    
                    # Convert to WAV
                    audio = AudioSegment.from_mp3(io.BytesIO(mp3_audio))
                    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                    audio = audio.speedup(playback_speed=1.1)
                    
                    wav_buffer = io.BytesIO()
                    audio.export(wav_buffer, format="wav")
                    wav_buffer.seek(0)
                    wav_bytes = wav_buffer.getvalue()
                    
                    logger.info(f"✅ [{idx+1}/{len(phrases)}] Converted to {len(wav_bytes)} bytes WAV")
                    
                    # ✅ ADD SIZE CHECK - Skip if too large for buffer
                    if len(wav_bytes) > 250000:  # 250KB safety margin
                        logger.warning(f"⚠️ [{idx+1}/{len(phrases)}] Audio too large ({len(wav_bytes)} bytes), splitting further")
                        # Split the phrase in half and process separately
                        words = phrase.split()
                        mid = len(words) // 2
                        part1 = ' '.join(words[:mid])
                        part2 = ' '.join(words[mid:])
                        
                        # Process first half
                        mp3_1 = await self.voice_component.create_audio_response_async(part1)
                        if mp3_1:
                            audio_1 = AudioSegment.from_mp3(io.BytesIO(mp3_1))
                            audio_1 = audio_1.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                            audio_1 = audio_1.speedup(playback_speed=1.1)
                            wav_1 = io.BytesIO()
                            audio_1.export(wav_1, format="wav")
                            await self.esp32_streamer._stream_wav_to_esp32(wav_1.getvalue(), websocket, client_id)
                        
                        # Process second half
                        mp3_2 = await self.voice_component.create_audio_response_async(part2)
                        if mp3_2:
                            audio_2 = AudioSegment.from_mp3(io.BytesIO(mp3_2))
                            audio_2 = audio_2.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                            audio_2 = audio_2.speedup(playback_speed=1.1)
                            wav_2 = io.BytesIO()
                            audio_2.export(wav_2, format="wav")
                            await self.esp32_streamer._stream_wav_to_esp32(wav_2.getvalue(), websocket, client_id)
                        
                        logger.info(f"✅ [{idx+1}/{len(phrases)}] Split and streamed")
                        continue
                    
                    # Normal streaming
                    await self.esp32_streamer._stream_wav_to_esp32(wav_bytes, websocket, client_id)
                    logger.info(f"✅ [{idx+1}/{len(phrases)}] Streaming complete")
                    
                except Exception as e:
                    logger.error(f"❌ [{idx+1}/{len(phrases)}] Error: {e}", exc_info=True)

            logger.info(f"✅ All {len(phrases)} phrases streamed sequentially")
                        
        except Exception as e:
            logger.error(f"❌ OpenAI streaming error: {e}", exc_info=True)
                
        
    def _extract_complete_sentences(self, text: str) -> list:
        """Extract complete sentences from text buffer"""
        import re
        # Split on sentence endings
        sentences = re.split(r'([.!?\n]+)', text)
        complete = []
        
        for i in range(0, len(sentences)-1, 2):
            if i+1 < len(sentences):
                complete.append(sentences[i] + sentences[i+1])
        
        return complete

    def _get_incomplete_sentence(self, text: str) -> str:
        """Get the incomplete sentence from buffer"""
        import re
        parts = re.split(r'[.!?\n]+', text)
        return parts[-1] if parts else ""
        
    def _combine_to_proper_wav(self, chunks: list, client_id: str) -> Optional[bytes]:
        """Combine WAV chunks into single WAV file"""
        try:
            settings = self.client_settings.get(client_id, {})
            sample_rate = settings.get("sample_rate", 44100)
            channels = settings.get("channels", 1)
            
            logger.info(f"Combining {len(chunks)} chunks (rate={sample_rate}, channels={channels})")
            
            all_audio_data = []
            
            for i, chunk in enumerate(chunks):
                try:
                    chunk_io = io.BytesIO(chunk)
                    with wave.open(chunk_io, 'rb') as wf:
                        audio_frames = wf.readframes(wf.getnframes())
                        all_audio_data.append(audio_frames)
                except Exception as e:
                    logger.debug(f"Chunk {i} error: {e}")
                    continue
            
            if not all_audio_data:
                return None
            
            combined_audio_data = b''.join(all_audio_data)
            logger.info(f"Combined → {len(combined_audio_data)} bytes raw audio")
            
            # Create proper WAV file
            output_buffer = io.BytesIO()
            with wave.open(output_buffer, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(combined_audio_data)
            
            result = output_buffer.getvalue()
            logger.info(f"✅ Created WAV: {len(result)} bytes")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Combining error: {e}", exc_info=True)
            return None
    
    async def _google_stt(self, audio_bytes: bytes) -> Optional[str]:
        """Google Speech Recognition"""
        if not self.voice_component:
            return None
        
        if len(audio_bytes) < 10000:
            logger.warning(f"⚠️ Audio too short: {len(audio_bytes)} bytes")
            return None
        
        try:
            logger.info(f"🎙️ Running STT on {len(audio_bytes)} bytes...")
            
            text = await asyncio.wait_for(
                self.voice_component.process_audio_to_text_async(
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