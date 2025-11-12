# audio_client_ws.py - Updated for complete workflow
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
    
    def __init__(self, server_url: str, client_id: str = "rpi_default"):
        self.server_url = server_url
        self.client_id = client_id
        
        # Audio settings
        self.sample_rate = 44100
        self.channels = 1
        self.chunk_size = 1024
        self.format = pyaudio.paInt16
        
        # Recording state
        self.is_recording = False
        self.audio_buffer = []
        self.chunk_counter = 0
        
        # PyAudio
        self.audio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        
        logger.info(f"Audio client initialized: {client_id}")
    
    async def connect(self):
        """Connect to server WebSocket"""
        try:
            self.websocket = await websockets.connect(self.server_url)
            logger.info(f"Connected to server: {self.server_url}")
            
            # Register client
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
            await asyncio.sleep(0.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
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
            
            # Open audio stream
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            logger.info("🎤 Recording started...")
            
            # Start streaming task
            await self._stream_audio()
            
        except Exception as e:
            logger.error(f"Recording error: {e}")
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
                    await self.websocket.send(json.dumps({
                        "type": "audio_chunk",
                        "audio": audio_base64,
                        "chunk_id": self.chunk_counter,
                        "timestamp": datetime.now().timestamp(),
                        "format": "audio/wav",
                        "sample_rate": self.sample_rate,
                        "channels": self.channels
                    }))
                    
                    self.chunk_counter += 1
                    
                    if self.chunk_counter % 20 == 0:  # Log every 20 chunks
                        logger.info(f"Sent {self.chunk_counter} audio chunks")
                
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
            
            # Send completion signal to trigger STT → OpenAI workflow
            if self.websocket:
                await self.websocket.send(json.dumps({
                    "type": "audio_complete",
                    "total_chunks": self.chunk_counter,
                    "timestamp": datetime.now().timestamp(),
                    "client_id": self.client_id
                }))
                logger.info("✅ Sent audio_complete signal to server")
            
            # Optionally save complete audio file
            await self._save_complete_audio()
            
        except Exception as e:
            logger.error(f"Stop recording error: {e}")
    
    async def _save_complete_audio(self):
        """Save the complete recording locally (optional backup)"""
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
    
    async def listen_for_responses(self):
        """Listen for STT results and responses from server"""
        try:
            while True:
                if not self.websocket:
                    break
                
                message = await self.websocket.recv()
                data = json.loads(message)
                
                if data.get("type") == "stt_result":
                    text = data.get("text", "")
                    logger.info(f"🎤 STT Result: '{text}'")
                    
                elif data.get("type") == "error":
                    logger.error(f"❌ Server error: {data.get('message')}")
                    
        except Exception as e:
            logger.error(f"Listen error: {e}")
    
    async def record_for_duration(self, duration_seconds: float):
        """
        Record for a specific duration
        Perfect for the complete workflow!
        """
        logger.info(f"🎤 Recording for {duration_seconds} seconds...")
        
        # Start recording
        recording_task = asyncio.create_task(self.start_recording())
        
        # Wait for duration
        await asyncio.sleep(duration_seconds)
        
        # Stop recording (this will trigger audio_complete message)
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
            self.stream.stop_stream()
            self.stream.close()
        
        self.audio.terminate()