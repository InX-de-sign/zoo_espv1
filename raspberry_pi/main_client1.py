# main_client.py - Fixed version based on working code
import asyncio
import logging
import json
from audio_client_ws import AudioStreamingClient
from tts_client import TTSClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MuseumRPiClient:
    """Complete Raspberry Pi client with full conversational workflow"""
    
    def __init__(self, server_url: str, client_id: str = "rpi_museum"):
        self.server_url = server_url
        self.client_id = client_id
        
        logger.info(f"Initializing client: {server_url}, ID: {client_id}")
        
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
        
        self.is_running = False
        self.stt_result = None
        self.response_received = False
        
    async def start(self):
        """Start both audio and TTS clients"""
        logger.info("="*60)
        logger.info("Starting Museum RPi Client...")
        logger.info("="*60)
        
        self.is_running = True
        
        # Connect audio client
        logger.info("Connecting audio client...")
        if not await self.audio_client.connect():
            logger.error("❌ Failed to connect audio client")
            return False
        logger.info("✅ Audio client connected")
        
        # Start TTS client in background
        logger.info("Starting TTS client...")
        tts_task = asyncio.create_task(self.tts_client.connect_and_listen())
        await asyncio.sleep(1)  # Give it time to connect
        logger.info("✅ TTS client started")
        
        # Start audio listening task
        logger.info("Starting audio listener...")
        audio_listen_task = asyncio.create_task(
            self._listen_for_audio_responses()
        )
        logger.info("✅ Audio listener started")
        
        print("\n" + "="*60)
        print("✅ Museum RPi Client started successfully!")
        print("="*60)
        print("Press Ctrl+C to stop\n")
        
        try:
            # Main interaction loop
            while self.is_running:
                print("="*60)
                print("Museum AI Assistant - Raspberry Pi")
                print("="*60)
                print("1. 🎤 Voice Conversation (COMPLETE WORKFLOW)")
                print("2. Record 5 seconds (basic)")
                print("3. Record 10 seconds (basic)")
                print("4. Send text query (working)")
                print("5. Exit")
                print("="*60)
                
                choice = await asyncio.get_event_loop().run_in_executor(
                    None, input, "Choose option: "
                )
                
                logger.info(f"User selected: {choice}")
                
                if choice == "1":
                    # COMPLETE WORKFLOW
                    await self.complete_conversation_workflow()
                    
                elif choice == "2":
                    logger.info("Recording 5 seconds...")
                    await self.audio_client.record_for_duration(5.0)
                    print("\n⏳ Audio sent to server, waiting for response...")
                    await asyncio.sleep(5)
                    
                elif choice == "3":
                    logger.info("Recording 10 seconds...")
                    await self.audio_client.record_for_duration(10.0)
                    print("\n⏳ Audio sent to server, waiting for response...")
                    await asyncio.sleep(5)
                    
                elif choice == "4":
                    # TEXT QUERY (THIS WORKS)
                    text = await asyncio.get_event_loop().run_in_executor(
                        None, input, "\nEnter your question: "
                    )
                    
                    logger.info(f"Sending text query: {text}")
                    if self.audio_client.websocket:
                        await self.audio_client.websocket.send(json.dumps({
                            "type": "text_query",
                            "text": text,
                            "client_id": self.client_id
                        }))
                        print("\n✅ Question sent, waiting for AI response...")
                        print("🔊 Listen for audio output...\n")
                        await asyncio.sleep(3)
                    else:
                        logger.error("❌ WebSocket not connected")
                    
                elif choice == "5":
                    logger.info("Exiting...")
                    self.is_running = False
                    break
                    
        except KeyboardInterrupt:
            logger.info("\n\nInterrupted by user")
        finally:
            # Cleanup
            logger.info("Cleaning up...")
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
        Complete workflow with better error handling
        """
        print("\n" + "🎤 " + "="*58)
        print("COMPLETE VOICE CONVERSATION WORKFLOW")
        print("="*60)
        
        self.stt_result = None
        self.response_received = False
        
        try:
            # STEP 1: Record audio
            print("\n🎙 STEP 1: Recording your voice...")
            print("🎤 Speak clearly into the microphone!")
            print("   Recording for 5 seconds...")
            print("-" * 60)
            
            logger.info("STEP 1: Starting recording...")
            await self.audio_client.record_for_duration(5.0)
            
            print("✅ Recording complete and sent to server!")
            logger.info("✅ Audio recording completed")
            
            # STEP 2: Wait for STT result
            print("\n🎙 STEP 2: Converting speech to text (Whisper API)...")
            print("⏳ Processing...")
            logger.info("STEP 2: Waiting for STT...")
            
            # Wait for STT with timeout
            timeout = 20
            start_time = asyncio.get_event_loop().time()
            
            while self.stt_result is None:
                await asyncio.sleep(0.2)
                elapsed = asyncio.get_event_loop().time() - start_time
                
                if elapsed > timeout:
                    logger.error("❌ STT TIMEOUT")
                    print("\n❌ TIMEOUT: No speech-to-text result received!")
                    print("\n🔍 Possible issues:")
                    print("   1. Server didn't receive audio properly")
                    print("   2. OpenAI Whisper API error on server")
                    print("   3. Audio was too quiet or unclear")
                    print("   4. Server not sending 'stt_result' message")
                    print("\n💡 Try:")
                    print("   - Speak louder and more clearly")
                    print("   - Check server logs for errors")
                    print("   - Test with option 4 (text query) to verify server is working")
                    return
            
            # Check if STT result is empty
            if not self.stt_result or not self.stt_result.strip():
                logger.warning("⚠️ Empty STT result received")
                print("\n⚠️ No speech detected or transcription empty!")
                print("💡 Tips:")
                print("   - Speak louder and more clearly")
                print("   - Check microphone connection")
                print("   - Reduce background noise")
                print("   - Try option 4 (text query) to test server")
                return
            
            print(f"\n✅ You said: '{self.stt_result}'")
            logger.info(f"✅ STT Result: '{self.stt_result}'")
            
            # STEP 3: Wait for OpenAI response
            print("\n🎙 STEP 3: Getting AI response...")
            print("🤖 Querying OpenAI GPT...")
            logger.info("STEP 3: Waiting for OpenAI response...")
            
            # STEP 4: Wait for streaming response
            print("\n🎙 STEP 4: Playing AI response...")
            print("🔊 Listen to your speakers...")
            print("-" * 60)
            logger.info("STEP 4: Waiting for audio playback...")
            
            # Wait for response with timeout
            response_timeout = 30
            start_time = asyncio.get_event_loop().time()
            
            while not self.response_received:
                await asyncio.sleep(0.5)
                elapsed = asyncio.get_event_loop().time() - start_time
                
                if elapsed > response_timeout:
                    logger.error("❌ No response received")
                    print("\n❌ No AI response received!")
                    print("\n🔍 Possible issues:")
                    print("   1. Server didn't send to OpenAI")
                    print("   2. OpenAI API error")
                    print("   3. Server not streaming response back")
                    print("\n💡 Check server logs for errors")
                    return
            
            # Give extra time for complete playback
            await asyncio.sleep(5)
            
            print("-" * 60)
            print("✅ Conversation complete!")
            print("="*60)
            logger.info("✅ Workflow completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Workflow error: {e}", exc_info=True)
            print(f"\n❌ Error: {e}")
        finally:
            self.stt_result = None
            self.response_received = False
    
    async def _listen_for_audio_responses(self):
        """Listen for server responses"""
        logger.info("👂 Audio response listener started")
        
        try:
            message_count = 0
            while True:
                if not self.audio_client.websocket:
                    await asyncio.sleep(1)
                    continue
                
                message = await self.audio_client.websocket.recv()
                message_count += 1
                
                logger.debug(f"📨 Message #{message_count}: {message[:200]}")
                
                data = json.loads(message)
                message_type = data.get("type")
                
                if message_type == "registered":
                    logger.info("✅ Client registered with server")
                    
                elif message_type == "stt_result":
                    # CRITICAL: STT result from server
                    text = data.get("text", "")
                    self.stt_result = text
                    logger.info(f"🎤 STT: '{text}'")
                    
                    if not text or not text.strip():
                        logger.warning("⚠️ Empty STT result!")
                    
                elif message_type == "stt_processing":
                    logger.info("⏳ Server processing speech...")
                    
                elif message_type == "openai_processing":
                    logger.info("🤖 Server querying OpenAI...")
                    
                elif message_type == "stream_start":
                    logger.info("🔊 Response stream starting...")
                    self.response_received = True
                    
                elif message_type == "response_chunk":
                    text = data.get("text", "")
                    self.response_received = True
                    logger.info(f"💬 Response: {text[:50]}...")
                    
                elif message_type == "stream_chunk":
                    text = data.get("text", "")
                    self.response_received = True
                    logger.info(f"💬 Stream: {text[:50]}...")
                    
                elif message_type == "response_complete":
                    total = data.get("total_sentences", 0)
                    logger.info(f"✅ Response complete ({total} parts)")
                    
                elif message_type == "error":
                    error_msg = data.get("message", "Unknown")
                    logger.error(f"❌ Server error: {error_msg}")
                    print(f"\n❌ Server Error: {error_msg}")
                    
                elif message_type == "status":
                    status = data.get("message", "")
                    logger.info(f"📊 {status}")
                    
                else:
                    logger.debug(f"Unknown message type: {message_type}")
                    
        except Exception as e:
            logger.error(f"❌ Listener error: {e}", exc_info=True)


async def main():
    """Main entry point"""
    SERVER_URL = "ws://100.88.240.42:8000"
    CLIENT_ID = "rpi_museum_1"
    
    print("="*60)
    print("🔊 Testing espeak-ng...")
    print("="*60)
    
    try:
        import subprocess
        # Enhanced espeak settings:
        # -v en-us+f3 = US English female voice (variant 3)
        # -s 140 = speed 140 words/min (slower than default 160)
        # -a 200 = amplitude/volume 200 (louder than default 100)
        # -p 50 = pitch 50 (default, adjust 0-99 for higher/lower)
        subprocess.run(
            ['espeak-ng', '-v', 'en-us+f3', '-s', '140', '-a', '200', '-p', '50', 
             'System ready. Museum assistant initialized.'],
            check=True,
            timeout=5
        )
        print("✅ espeak-ng working with enhanced voice!\n")
        print("   Voice: Female (en-us+f3)")
        print("   Speed: 140 words/min (slower)")
        print("   Volume: 200 (louder)")
        print("   Pitch: 50 (natural)\n")
    except Exception as e:
        print(f"⚠️ espeak-ng test failed: {e}")
        print("TTS may not work properly\n")
    
    print(f"🚀 Starting Museum Client...")
    print(f"   Server: {SERVER_URL}")
    print(f"   Client ID: {CLIENT_ID}\n")
    
    client = MuseumRPiClient(SERVER_URL, CLIENT_ID)
    await client.start()


if __name__ == "__main__":
    asyncio.run(main())