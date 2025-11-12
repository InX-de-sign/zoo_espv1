# main_client.py - Complete workflow (client-side only)
import asyncio
import logging
import json
from audio_client_ws import AudioStreamingClient
from tts_client import TTSClient
from wakeword_detector import PorcupineWakeDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MuseumRPiClient:
    """Complete Raspberry Pi client with full conversational workflow"""
    
    def __init__(self, server_url: str, client_id: str = "rpi_museum"):
        self.server_url = server_url
        self.client_id = client_id
        
        # Initialize audio client
        self.audio_client = AudioStreamingClient(
            f"{server_url}/ws/audio",
            client_id
        )
        
        # Initialize TTS client
        self.tts_client = TTSClient(
            f"{server_url}/ws/tts",
            client_id
        )
        
        # initialize detector
        self.wake_detector = None
        self.wake_detected = False
        
        self.is_running = False
        self.waiting_for_response = False
        self.stt_result = None
        
    async def start(self):
        """Start both audio and TTS clients"""
        logger.info("Starting Museum RPi Client...")
        
        self.is_running = True
        
        # Connect audio client
        if not await self.audio_client.connect():
            logger.error("Failed to connect audio client")
            return False
        
        # Start TTS client in background
        tts_task = asyncio.create_task(self.tts_client.connect_and_listen())
        
        # Start audio listening task with custom handler
        audio_listen_task = asyncio.create_task(
            self._listen_for_audio_responses()
        )
        
        logger.info("✅ Museum RPi Client started successfully!")
        logger.info("Press Ctrl+C to stop")
        
        try:
            # Main interaction loop
            while self.is_running:
                print("\n" + "="*50)
                print("Museum AI Assistant - Raspberry Pi")
                print("="*50)
                print("1. 🎤 Voice Conversation (COMPLETE WORKFLOW)")
                print("2. Record 5 seconds")
                print("3. Record 10 seconds")
                print("4. Manual recording (press Enter to stop)")
                print("5. Send text query")
                print("6. Exit")
                print("="*50)
                
                choice = await asyncio.get_event_loop().run_in_executor(
                    None, input, "Choose option: "
                )
                
                if choice == "1":
                    # *** COMPLETE CONVERSATIONAL WORKFLOW ***
                    await self.complete_conversation_workflow()
                    
                elif choice == "2":
                    await self.audio_client.record_for_duration(5.0)
                    print("⏳ Waiting for server response...")
                    await asyncio.sleep(3)  # Wait for processing
                    
                elif choice == "3":
                    await self.audio_client.record_for_duration(10.0)
                    print("⏳ Waiting for server response...")
                    await asyncio.sleep(3)
                    
                elif choice == "4":
                    print("🎤 Recording... Press Enter to stop")
                    recording_task = asyncio.create_task(
                        self.audio_client.start_recording()
                    )
                    
                    await asyncio.get_event_loop().run_in_executor(None, input)
                    
                    await self.audio_client.stop_recording()
                    recording_task.cancel()
                    print("⏳ Waiting for server response...")
                    await asyncio.sleep(3)
                    
                elif choice == "5":
                    text = await asyncio.get_event_loop().run_in_executor(
                        None, input, "Enter your question: "
                    )
                    
                    if self.audio_client.websocket:
                        await self.audio_client.websocket.send(json.dumps({
                            "type": "text_query",
                            "text": text,
                            "client_id": self.client_id
                        }))
                        logger.info(f"Sent text query: {text}")
                        print("⏳ Waiting for AI response...")
                        await asyncio.sleep(2)
                    
                elif choice == "6":
                    logger.info("Exiting...")
                    self.is_running = False
                    break
                    
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            # Cleanup
            self.audio_client.cleanup()
            self.tts_client.shutdown()
            
            tts_task.cancel()
            audio_listen_task.cancel()
            
            try:
                await tts_task
            except asyncio.CancelledError:
                pass
            try:
                await audio_listen_task
            except asyncio.CancelledError:
                pass

    async def complete_conversation_workflow(self):
        """
        🎯 COMPLETE WORKFLOW:
        1. Record audio from microphone
        2. Send to server → Server does STT (speech-to-text)
        3. Server sends to OpenAI
        4. Server streams response back
        5. TTS plays response via espeak-ng
        """
        print("\n" + "🎤 " + "="*48)
        print("COMPLETE VOICE CONVERSATION WORKFLOW")
        print("="*50)
        
        self.waiting_for_response = True
        self.stt_result = None
        
        try:
            # STEP 1: Record audio
            print("\n📍 STEP 1: Recording your voice...")
            print("🎤 Speak now! (Recording for 5 seconds)")
            print("-" * 50)
            
            await self.audio_client.record_for_duration(5.0)
            
            print("✅ Recording complete!")
            
            # STEP 2: Wait for STT result from server
            print("\n📍 STEP 2: Converting speech to text...")
            print("⏳ Processing with OpenAI Whisper...")
            
            # Wait for STT result (server will send it back)
            timeout = 15  # 15 second timeout
            start_time = asyncio.get_event_loop().time()
            
            while self.stt_result is None:
                await asyncio.sleep(0.1)
                if asyncio.get_event_loop().time() - start_time > timeout:
                    print("❌ Timeout waiting for STT result")
                    return
            
            print(f"✅ You said: '{self.stt_result}'")
            
            # STEP 3: Server automatically sends to OpenAI
            print("\n📍 STEP 3: Getting AI response from OpenAI...")
            print("🤖 Processing your question...")
            
            # STEP 4: Wait for response to start streaming
            print("\n📍 STEP 4: Receiving and playing AI response...")
            print("🔊 Playing through speakers...")
            print("-" * 50)
            
            # The TTS client will automatically receive and play the response
            # Wait for the response to complete (give enough time)
            await asyncio.sleep(20)  # Adjust based on expected response length
            
            print("-" * 50)
            print("✅ Conversation complete!")
            print("="*50)
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            print(f"❌ Error: {e}")
        finally:
            self.waiting_for_response = False
    
    async def _listen_for_audio_responses(self):
        """Listen for server responses and update workflow status"""
        try:
            while True:
                if not self.audio_client.websocket:
                    await asyncio.sleep(1)
                    continue
                
                message = await self.audio_client.websocket.recv()
                data = json.loads(message)
                
                message_type = data.get("type")
                
                if message_type == "stt_result":
                    # Speech-to-text result from server
                    text = data.get("text", "")
                    self.stt_result = text  # Store for workflow
                    logger.info(f"🎤 STT: '{text}'")
                    
                elif message_type == "stt_processing":
                    logger.info("⏳ Server processing speech...")
                    
                elif message_type == "openai_processing":
                    logger.info("🤖 Getting OpenAI response...")
                    
                elif message_type == "stream_start":
                    logger.info("🔊 Starting audio playback...")
                    
                elif message_type == "response_chunk":
                    # Server sending response chunks (for logging)
                    text = data.get("text", "")
                    logger.info(f"💬 AI: {text[:50]}...")
                    
                elif message_type == "response_complete":
                    total = data.get("total_sentences", 0)
                    logger.info(f"✅ Response complete ({total} sentences)")
                    
                elif message_type == "error":
                    error_msg = data.get("message", "Unknown error")
                    logger.error(f"❌ Server error: {error_msg}")
                    print(f"\n❌ Error: {error_msg}")
                    
                elif message_type == "status":
                    status_msg = data.get("message", "")
                    logger.info(f"📊 {status_msg}")
                    
        except Exception as e:
            logger.error(f"Listen error: {e}")


async def main():
    """Main entry point"""
    # CHANGE THIS to your server IP
    SERVER_URL = "ws://100.88.240.42:8000"  # Replace with your PC's IP
    CLIENT_ID = "rpi_museum_1"
    
    print("="*50)
    print("🔊 Testing espeak-ng...")
    print("="*50)
    
    # Quick espeak test
    try:
        import subprocess
        subprocess.run(
            ['espeak-ng', '-v', 'en-us', '-s', '160', 'System ready'],
            check=True,
            timeout=5
        )
        print("✅ espeak-ng working!")
    except Exception as e:
        print(f"⚠️ espeak-ng test failed: {e}")
        print("TTS may not work properly")
    
    print("\n🚀 Starting Museum Client...")
    client = MuseumRPiClient(SERVER_URL, CLIENT_ID)
    await client.start()


if __name__ == "__main__":
    asyncio.run(main())