# tts_client.py - UPDATED VERSION with espeak-ng
import asyncio
import json
import subprocess
import logging
from typing import Optional
import websockets
import queue
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TTSClient:
    """Raspberry Pi client for receiving and playing streaming text responses"""
    
    def __init__(self, server_url: str, client_id: str):
        self.server_url = server_url
        self.client_id = client_id
        self.tts_queue = queue.Queue()
        self.is_playing = False
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        
        # Start TTS playback thread
        self.playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self.playback_thread.start()
        
        logger.info(f"TTS Client initialized for {client_id}")
    
    async def connect_and_listen(self):
        """Connect to server and listen for streaming text responses"""
        try:
            async with websockets.connect(self.server_url) as websocket:
                self.websocket = websocket
                logger.info(f"Connected to server: {self.server_url}")
                
                # Send registration
                await websocket.send(json.dumps({
                    "type": "register",
                    "client_id": self.client_id,
                    "role": "tts_client"
                }))
                
                # Listen for streaming responses
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        if data.get("type") == "stream_chunk":
                            # Received streaming text chunk
                            text = data.get("text", "")
                            sentence_num = data.get("sentence_number", 0)
                            
                            logger.info(f"Received sentence {sentence_num}: {text}")
                            
                            # Add to TTS queue for immediate playback
                            self.tts_queue.put({
                                "text": text,
                                "sentence_number": sentence_num
                            })
                            
                        elif data.get("type") == "stream_complete":
                            total = data.get("total_sentences", 0)
                            logger.info(f"Response complete: {total} sentences")
                            
                        elif data.get("type") == "error":
                            logger.error(f"Server error: {data.get('message')}")
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {e}")
                    except Exception as e:
                        logger.error(f"Message processing error: {e}")
                        
        except Exception as e:
            logger.error(f"Connection error: {e}")
            # Attempt reconnection
            await asyncio.sleep(5)
            await self.connect_and_listen()
    
    def _playback_worker(self):
        """Background thread for sequential TTS playback"""
        logger.info("TTS playback worker started")
        
        while True:
            try:
                # Get next text from queue (blocking)
                item = self.tts_queue.get()
                
                if item is None:  # Shutdown signal
                    break
                
                text = item["text"]
                sentence_num = item["sentence_number"]
                
                if not text or not text.strip():
                    continue
                
                self.is_playing = True
                logger.info(f"Playing sentence {sentence_num}: {text[:50]}...")
                
                # Use espeak-ng for TTS (blocking call)
                self._speak_with_espeak_ng(text)
                
                self.is_playing = False
                self.tts_queue.task_done()
                
            except Exception as e:
                logger.error(f"Playback error: {e}")
                self.is_playing = False
    
    def _speak_with_espeak_ng(self, text: str, voice: str = 'en', speed: int = 175):
        """
        Use espeak-ng for TTS - simplified version that works
        """
        if not text.strip():
            return
        
        try:
            # Simpler approach - like your friend's code
            cmd = ['espeak-ng', '-v', voice, '-s', str(speed), text]
            subprocess.call(cmd)  # Blocking call, waits for completion
            logger.info(f"✅ espeak-ng completed for: {text[:30]}...")
            
        except FileNotFoundError:
            logger.error("espeak-ng not found! Install: sudo apt-get install espeak-ng")
        except Exception as e:
            logger.error(f"TTS error: {e}")    

    def shutdown(self):
        """Cleanup resources"""
        logger.info("Shutting down TTS client...")
        self.tts_queue.put(None)  # Signal playback thread to stop
        if self.playback_thread.is_alive():
            self.playback_thread.join(timeout=2)


# Example usage
async def main():
    """Example TTS client usage"""
    # Replace with your server URL
    server_url = "ws://YOUR_SERVER_IP:8000/ws/tts"
    client_id = "rpi_client_1"
    
    tts_client = TTSClient(server_url, client_id)
    
    try:
        await tts_client.connect_and_listen()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        tts_client.shutdown()


if __name__ == "__main__":
    asyncio.run(main())