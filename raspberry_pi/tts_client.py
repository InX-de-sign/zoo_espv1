# tts_client.py - With extensive debugging
import asyncio
import json
import subprocess
import logging
from typing import Optional
import websockets
import queue
import threading

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TTSClient:
    """Raspberry Pi client for receiving and playing streaming text responses"""
    
    def __init__(self, server_url: str, client_id: str):
        self.server_url = server_url
        self.client_id = client_id
        self.tts_queue = queue.Queue()
        self.is_playing = False
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.sentences_played = 0
        
        logger.info(f"🔧 TTS Client initializing for {client_id}")
        logger.debug(f"Server URL: {server_url}")
        
        # Start TTS playback thread
        self.playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self.playback_thread.start()
        logger.info("✅ TTS playback thread started")
    
    async def connect_and_listen(self):
        """Connect to server and listen for streaming text responses"""
        try:
            logger.info(f"🔌 Connecting to TTS server: {self.server_url}")
            
            async with websockets.connect(self.server_url) as websocket:
                self.websocket = websocket
                logger.info(f"✅ TTS connected to server: {self.server_url}")
                
                # Send registration
                register_msg = {
                    "type": "register",
                    "client_id": self.client_id,
                    "role": "tts_client"
                }
                logger.debug(f"📤 Sending TTS registration: {register_msg}")
                
                await websocket.send(json.dumps(register_msg))
                logger.info("✅ TTS registration sent")
                
                # Listen for streaming responses
                message_count = 0
                while True:
                    try:
                        logger.debug("👂 Waiting for TTS message...")
                        message = await websocket.recv()
                        message_count += 1
                        
                        logger.debug(f"📨 TTS Message #{message_count}: {message[:200]}")
                        
                        data = json.loads(message)
                        message_type = data.get("type")
                        
                        logger.info(f"📨 TTS Message type: {message_type}")
                        
                        if message_type == "registered":
                            logger.info("✅ TTS client registered with server")
                        
                        elif message_type == "stream_chunk":
                            # Received streaming text chunk
                            text = data.get("text", "")
                            sentence_num = data.get("sentence_number", 0)
                            
                            logger.info(f"💬 Received sentence {sentence_num}: {text}")
                            print(f"\n🔊 Playing: {text}")
                            
                            # Add to TTS queue for immediate playback
                            self.tts_queue.put({
                                "text": text,
                                "sentence_number": sentence_num
                            })
                            logger.debug(f"Added to TTS queue (queue size: {self.tts_queue.qsize()})")
                            
                        elif message_type == "stream_complete":
                            total = data.get("total_sentences", 0)
                            logger.info(f"✅ Response stream complete: {total} sentences")
                            print(f"✅ Response complete ({total} sentences)")
                            
                        elif message_type == "error":
                            error_msg = data.get("message", "")
                            logger.error(f"❌ TTS Server error: {error_msg}")
                            print(f"❌ Error: {error_msg}")
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ JSON decode error: {e}")
                        logger.error(f"Raw message: {message}")
                    except Exception as e:
                        logger.error(f"❌ Message processing error: {e}", exc_info=True)
                        
        except Exception as e:
            logger.error(f"❌ TTS Connection error: {e}", exc_info=True)
            print(f"❌ TTS connection failed: {e}")
            # Attempt reconnection
            logger.info("🔄 Attempting to reconnect in 5 seconds...")
            await asyncio.sleep(5)
            await self.connect_and_listen()
    
    def _playback_worker(self):
        """Background thread for sequential TTS playback"""
        logger.info("🔊 TTS playback worker started")
        
        while True:
            try:
                # Get next text from queue (blocking)
                logger.debug("Waiting for item in TTS queue...")
                item = self.tts_queue.get()
                
                if item is None:  # Shutdown signal
                    logger.info("🛑 TTS playback worker shutting down")
                    break
                
                text = item["text"]
                sentence_num = item["sentence_number"]
                
                if not text or not text.strip():
                    logger.warning(f"⚠️ Empty text for sentence {sentence_num}, skipping")
                    continue
                
                self.is_playing = True
                self.sentences_played += 1
                
                logger.info(f"🔊 Playing sentence {sentence_num}: {text[:50]}...")
                
                # Use espeak-ng for TTS (blocking call)
                self._speak_with_espeak_ng(text)
                
                self.is_playing = False
                self.tts_queue.task_done()
                
                logger.debug(f"✅ Finished playing sentence {sentence_num}")
                
            except Exception as e:
                logger.error(f"❌ Playback error: {e}", exc_info=True)
                self.is_playing = False
    
    def _speak_with_espeak_ng(self, text: str, voice: str = 'en', speed: int = 175):
        """
        Use espeak-ng for TTS
        """
        if not text.strip():
            logger.warning("⚠️ Empty text passed to espeak, skipping")
            return
        
        try:
            logger.debug(f"🔊 Calling espeak-ng with voice={voice}, speed={speed}")
            logger.debug(f"Text: {text}")
            
            # Simple approach - like your friend's code
            cmd = ['espeak-ng', '-v', voice, '-s', str(speed), text]
            
            logger.debug(f"Command: {' '.join(cmd)}")
            
            result = subprocess.call(cmd)  # Blocking call, waits for completion
            
            if result == 0:
                logger.info(f"✅ espeak-ng completed successfully")
            else:
                logger.warning(f"⚠️ espeak-ng returned code: {result}")
            
        except FileNotFoundError:
            logger.error("❌ espeak-ng not found! Install: sudo apt-get install espeak-ng")
            print("❌ espeak-ng not installed!")
        except Exception as e:
            logger.error(f"❌ TTS error: {e}", exc_info=True)    

    def shutdown(self):
        """Cleanup resources"""
        logger.info("🧹 Shutting down TTS client...")
        logger.info(f"Total sentences played: {self.sentences_played}")
        
        self.tts_queue.put(None)  # Signal playback thread to stop
        
        if self.playback_thread.is_alive():
            logger.debug("Waiting for playback thread to finish...")
            self.playback_thread.join(timeout=2)
            
        logger.info("✅ TTS client shutdown complete")


# Example usage
async def main():
    """Example TTS client usage"""
    server_url = "ws://YOUR_SERVER_IP:8000/ws/tts"
    client_id = "rpi_client_1"
    
    logger.info("Starting TTS client test...")
    
    tts_client = TTSClient(server_url, client_id)
    
    try:
        await tts_client.connect_and_listen()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        tts_client.shutdown()


if __name__ == "__main__":
    asyncio.run(main())