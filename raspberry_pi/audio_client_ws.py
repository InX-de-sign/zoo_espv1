# audio_client_ws.py - FIXED with ReSpeaker device 0
import asyncio
import json
import base64
import logging
import pyaudio
import wave
import io
from datetime import datetime
import websockets
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioStreamingClient:
    """Records audio on Raspberry Pi and streams to server via WebSocket"""
    
    def __init__(self, server_url: str, client_id: str = "rpi_default", device_index: int = 0):
        self.server_url = server_url
        self.client_id = client_id
        
        # ✅ FIXED: Audio settings for ReSpeaker device 0
        self.sample_rate = 16000  # ReSpeaker Lite supports 16000 Hz
        self.channels = 1
        self.chunk_size = 1024
        self.format = pyaudio.paInt16
        self.device_index = device_index  # ✅ Store device index (default 0 for ReSpeaker)
        
        # Recording state
        self.is_recording = False
        self.audio_buffer = []
        self.chunk_counter = 0
        
        # PyAudio
        self.audio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        
        logger.info(f"Audio client initialized: {client_id}")
        logger.info(f"  Device index: {self.device_index}")
        logger.info(f"  Sample rate: {self.sample_rate} Hz")
    
    async def connect(self, max_retries: int = 3, retry_delay: float = 2.0):
        """Connect to server WebSocket with retry logic"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to {self.server_url} (attempt {attempt + 1}/{max_retries})...")
                
                self.websocket = await asyncio.wait_for(
                    websockets.connect(
                        self.server_url,
                        ping_interval=20,
                        ping_timeout=10,
                        close_timeout=10,
                        open_timeout=30,
                        max_size=10 * 1024 * 1024,
                    ),
                    timeout=30.0
                )
                
                logger.info(f"✅ Connected to server: {self.server_url}")
                
                # Register client
                logger.info(f"Registering client: {self.client_id}")
                await self.websocket.send(json.dumps({
                    "type": "register",
                    "client_id": self.client_id,
                    "audio_settings": {
                        "sample_rate": self.sample_rate,
                        "channels": self.channels,
                        "format": "audio/wav"
                    }
                }))
                
                # Wait for registration confirmation
                try:
                    response = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=5.0
                    )
                    logger.info(f"✅ Registration response: {response[:100]}")
                except asyncio.TimeoutError:
                    logger.warning("⚠️ No registration response (continuing anyway)")
                
                return True
                
            except asyncio.TimeoutError:
                logger.error(f"❌ Connection timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    logger.info(f"⏳ Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("❌ All connection attempts failed")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    return False
        
        return False
    
    async def start_recording(self):
        """Start recording and streaming audio"""
        if self.is_recording:
            logger.warning("Already recording")
            return
        
        try:
            self.is_recording = True
            self.audio_buffer = []
            self.chunk_counter = 0
            
            # ✅ FIXED: Open audio stream with ReSpeaker device
            logger.info(f"Opening audio stream:")
            logger.info(f"  Device index: {self.device_index}")
            logger.info(f"  Sample rate: {self.sample_rate} Hz")
            logger.info(f"  Channels: {self.channels}")
            
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,  # ✅ Use ReSpeaker!
                frames_per_buffer=self.chunk_size
            )
            
            logger.info("🎤 Recording started...")
            
            # Start streaming task
            await self._stream_audio()
            
        except Exception as e:
            logger.error(f"❌ Recording error: {e}")
            logger.error(f"   Make sure ReSpeaker Lite is connected")
            logger.error(f"   Try: arecord -l")
            self.is_recording = False
    
    async def _stream_audio(self):
        """Stream audio chunks to server"""
        try:
            while self.is_recording:
                # Read audio chunk
                audio_data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                self.audio_buffer.append(audio_data)
                
                # Convert to WAV format for this chunk
                wav_chunk = self._create_wav_chunk(audio_data)
                
                # Encode to base64
                audio_base64 = base64.b64encode(wav_chunk).decode('utf-8')
                
                # Send to server
                if self.websocket:
                    try:
                        await asyncio.wait_for(
                            self.websocket.send(json.dumps({
                                "type": "audio_chunk",
                                "audio": audio_base64,
                                "chunk_id": self.chunk_counter,
                                "timestamp": datetime.now().timestamp(),
                                "format": "audio/wav",
                                "sample_rate": self.sample_rate,
                                "channels": self.channels
                            })),
                            timeout=5.0
                        )
                        
                        self.chunk_counter += 1
                        
                        if self.chunk_counter % 20 == 0:
                            logger.info(f"Sent {self.chunk_counter} audio chunks")
                            
                    except asyncio.TimeoutError:
                        logger.error(f"⚠️ Timeout sending chunk {self.chunk_counter}")
                    except Exception as e:
                        logger.error(f"⚠️ Error sending chunk {self.chunk_counter}: {e}")
                
                # Small delay
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Streaming error: {e}")
        finally:
            await self.stop_recording()
    
    def _create_wav_chunk(self, audio_data: bytes) -> bytes:
        """Convert raw audio to WAV format"""
        wav_buffer = io.BytesIO()
        
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.format))
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data)
        
        return wav_buffer.getvalue()
    
    async def stop_recording(self):
        """Stop recording and send completion signal"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        try:
            # Close audio stream
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            
            logger.info(f"🛑 Recording stopped. Total chunks: {self.chunk_counter}")
            
            # Send completion signal
            if self.websocket:
                await self.websocket.send(json.dumps({
                    "type": "audio_complete",
                    "total_chunks": self.chunk_counter,
                    "timestamp": datetime.now().timestamp(),
                    "client_id": self.client_id
                }))
                logger.info("✅ Sent audio_complete signal to server")
            
            # Save complete audio file
            await self._save_complete_audio()
            
        except Exception as e:
            logger.error(f"Stop recording error: {e}")
    
    async def _save_complete_audio(self):
        """Save the complete recording locally"""
        if not self.audio_buffer:
            return
        
        try:
            import os
            folder = "audioInput"
            os.makedirs(folder, exist_ok=True)
            filename = os.path.join(
                folder, 
                f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            )
            
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.format))
                wf.setframerate(self.sample_rate)
                for chunk in self.audio_buffer:
                    wf.writeframes(chunk)
            
            logger.info(f"💾 Saved recording: {filename}")
        except Exception as e:
            logger.error(f"Save error: {e}")
    
    async def record_for_duration(self, duration_seconds: float):
        """Record for a specific duration"""
        logger.info(f"🎤 Recording for {duration_seconds} seconds...")
        
        # Start recording
        recording_task = asyncio.create_task(self.start_recording())
        
        # Wait for duration
        await asyncio.sleep(duration_seconds)
        
        # Stop recording
        await self.stop_recording()
        
        # Cancel recording task
        recording_task.cancel()
        try:
            await recording_task
        except asyncio.CancelledError:
            pass
    
    def cleanup(self):
        """Cleanup resources"""
        logger.info("🧹 Cleaning up audio client...")
        
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        
        try:
            self.audio.terminate()
        except:
            pass