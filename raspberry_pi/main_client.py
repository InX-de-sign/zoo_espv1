# main_client.py - FIXED: Use specific ReSpeaker device index
import asyncio
import logging
import json
import os
import pyaudio
from audio_client_ws import AudioStreamingClient
from tts_client import TTSClient
from wakeword_detector import PorcupineWakeDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_respeaker_device():
    """Find ReSpeaker device index"""
    pa = pyaudio.PyAudio()
    respeaker_index = None
    
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        name = info.get('name', '').lower()
        
        if 'respeaker' in name and info['maxInputChannels'] > 0:
            respeaker_index = i
            logger.info(f"✅ Found ReSpeaker at device index {i}: {info['name']}")
            break
    
    pa.terminate()
    return respeaker_index

class MuseumRPiClient:
    """Complete Raspberry Pi client with wake word detection"""
    
    def __init__(self, server_url: str, client_id: str = "rpi_museum"):
        self.server_url = server_url
        self.client_id = client_id
        
        # ✅ Find ReSpeaker device
        self.respeaker_device = find_respeaker_device()
        if self.respeaker_device is None:
            logger.warning("⚠️ ReSpeaker not found, using default device")
        
        # Initialize audio client with specific device
        self.audio_client = AudioStreamingClient(
            f"{server_url}/ws/audio",
            client_id,
            device_index=self.respeaker_device  # ✅ Pass device index
        )
        
        self.tts_client = TTSClient(
            f"{server_url}/ws/tts",
            client_id
        )
        
        self.wake_detector = None
        self.wake_detected = False
        
        self.is_running = False
        self.waiting_for_response = False
        self.stt_result = None
        
        self.tts_task = None
        self.audio_listen_task = None
        
    async def start(self):
        """Start audio, TTS, and wake word detector"""
        logger.info("Starting Museum RPi Client...")
        
        self.is_running = True
        
        if not await self.audio_client.connect():
            logger.error("Failed to connect audio client")
            return False
        
        self.tts_task = asyncio.create_task(self._run_tts_with_reconnect())
        
        self.audio_listen_task = asyncio.create_task(
            self._listen_for_audio_responses()
        )
        
        # Initialize wake word detector with SAME device
        try:
            self.wake_detector = PorcupineWakeDetector(
                on_detect=self._on_wake_word_detected,
                keyword_name="hey bro",
                device_index=self.respeaker_device,  # ✅ Use same device!
                access_key="sOFyd6WFRhOJe4FUKluZRSMSMCwRXhuMq4MDH568UYto7wMMl397CQ=="
            )
            self.wake_detector.start()
            logger.info("✅ Wake word detector started!")
        except Exception as e:
            logger.error(f"⚠️ Wake word detector failed: {e}")
            logger.info("Continuing without wake word detection")
        
        logger.info("✅ Museum RPi Client started successfully!")
        logger.info("Press Ctrl+C to stop")
        
        try:
            while self.is_running:
                print("\n" + "="*50)
                print("Museum AI Assistant - Raspberry Pi")
                print("="*50)
                print("1. 🎤 Voice Conversation with WAKE WORD (say 'Hey bro')")
                print("2. 🎤 Voice Conversation (NO wake word, immediate)")
                print("3. Record 5 seconds")
                print("4. Record 10 seconds")
                print("5. Manual recording (press Enter to stop)")
                print("6. Send text query")
                print("7. Exit")
                print("="*50)
                
                choice = await asyncio.get_event_loop().run_in_executor(
                    None, input, "Choose option: "
                )
                
                if choice == "1":
                    await self.conversation_with_wake_word()
                    
                elif choice == "2":
                    await self.complete_conversation_workflow()
                    
                elif choice == "3":
                    if self.wake_detector:
                        self.wake_detector.pause()
                    
                    await self.audio_client.record_for_duration(5.0)
                    print("⏳ Waiting for server response...")
                    await asyncio.sleep(3)
                    
                    if self.wake_detector:
                        self.wake_detector.resume()
                    
                elif choice == "4":
                    if self.wake_detector:
                        self.wake_detector.pause()
                    
                    await self.audio_client.record_for_duration(10.0)
                    print("⏳ Waiting for server response...")
                    await asyncio.sleep(3)
                    
                    if self.wake_detector:
                        self.wake_detector.resume()
                    
                elif choice == "5":
                    if self.wake_detector:
                        self.wake_detector.pause()
                    
                    print("🎤 Recording... Press Enter to stop")
                    recording_task = asyncio.create_task(
                        self.audio_client.start_recording()
                    )
                    
                    await asyncio.get_event_loop().run_in_executor(None, input)
                    
                    await self.audio_client.stop_recording()
                    recording_task.cancel()
                    print("⏳ Waiting for server response...")
                    await asyncio.sleep(3)
                    
                    if self.wake_detector:
                        self.wake_detector.resume()
                    
                elif choice == "6":
                    await self.send_text_query()
                    
                elif choice == "7":
                    logger.info("Exiting...")
                    self.is_running = False
                    break
                    
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            await self._cleanup()

    async def send_text_query(self):
        text = await asyncio.get_event_loop().run_in_executor(
            None, input, "Enter your question: "
        )
        
        if not text or not text.strip():
            print("❌ Empty query, skipping")
            return
        
        try:
            print(f"\n📤 Sending query: '{text}'")
            
            if self.audio_client.websocket:
                await self.audio_client.websocket.send(json.dumps({
                    "type": "text_query",
                    "text": text,
                    "client_id": self.client_id
                }))
                logger.info(f"Sent text query: {text}")
                
                print("⏳ Waiting for AI response...")
                print("🔊 Listen for audio response on speakers...")
                
                await asyncio.sleep(10)
                
            else:
                print("❌ Not connected to server")
                
        except Exception as e:
            logger.error(f"Error sending text query: {e}")
            print(f"❌ Error: {e}")

    async def _run_tts_with_reconnect(self):
        reconnect_delay = 2
        max_reconnect_delay = 30
        
        while self.is_running:
            try:
                logger.info("🔊 Starting TTS client...")
                await self.tts_client.connect_and_listen()
            except Exception as e:
                if self.is_running:
                    logger.warning(f"⚠️ TTS client disconnected: {e}")
                    logger.info(f"🔄 Reconnecting in {reconnect_delay} seconds...")
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
                else:
                    break
            else:
                reconnect_delay = 2

    async def _cleanup(self):
        logger.info("🧹 Cleaning up...")
        
        if self.wake_detector:
            self.wake_detector.stop()
            logger.info("✅ Wake word detector stopped")
        
        self.audio_client.cleanup()
        logger.info("✅ Audio client cleaned up")
        
        self.tts_client.shutdown()
        logger.info("✅ TTS client shutdown")
        
        if self.tts_task:
            self.tts_task.cancel()
            try:
                await self.tts_task
            except asyncio.CancelledError:
                pass
            logger.info("✅ TTS task cancelled")
        
        if self.audio_listen_task:
            self.audio_listen_task.cancel()
            try:
                await self.audio_listen_task
            except asyncio.CancelledError:
                pass
            logger.info("✅ Audio listen task cancelled")
        
        logger.info("🎉 Cleanup complete!")

    def _on_wake_word_detected(self):
        if not self.waiting_for_response and self.is_running:
            logger.info("🎤 Wake word detected: 'Hey bro'!")
            print("\n🎤 Wake word detected! Starting conversation...")
            self.wake_detected = True

    async def conversation_after_wake_word(self):
        if self.wake_detector:
            self.wake_detector.pause()
            logger.info("⏸️ Wake word detector paused - waiting for microphone release...")
            await asyncio.sleep(1.0)  # Reduced from 2.0 since we're using same device
            logger.info("✅ Microphone should now be available")
        
        print("\n" + "🎤 " + "="*48)
        print("WAKE WORD DETECTED - VOICE CONVERSATION")
        print("="*50)
        
        self.waiting_for_response = True
        self.stt_result = None
        self.wake_detected = False
        
        try:
            print("\n📍 STEP 1: Recording your voice...")
            print("🎤 Speak now! (Recording for 5 seconds)")
            print("-" * 50)
            
            await self.audio_client.record_for_duration(5.0)
            
            print("✅ Recording complete!")
            
            print("\n📍 STEP 2: Converting speech to text...")
            print("⏳ Processing with OpenAI Whisper...")
            
            timeout = 15
            start_time = asyncio.get_event_loop().time()
            
            while self.stt_result is None:
                await asyncio.sleep(0.1)
                if asyncio.get_event_loop().time() - start_time > timeout:
                    print("❌ Timeout waiting for STT result")
                    return
            
            print(f"✅ You said: '{self.stt_result}'")
            
            print("\n📍 STEP 3: Getting AI response from OpenAI...")
            print("🤖 Processing your question...")
            
            print("\n📍 STEP 4: Receiving and playing AI response...")
            print("🔊 Playing through speakers...")
            print("-" * 50)
            
            await asyncio.sleep(20)
            
            print("-" * 50)
            print("✅ Conversation complete!")
            print("="*50)
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            print(f"❌ Error: {e}")
        finally:
            self.waiting_for_response = False
            
            if self.wake_detector:
                self.wake_detector.resume()
                logger.info("👂 Wake word detector resumed")

    async def conversation_with_wake_word(self):
        if not self.wake_detector:
            print("❌ Wake word detector not available. Use option 2 instead.")
            return
        
        print("\n👂 Listening for wake word: 'Hey bro'")
        print("Say 'Hey bro' to start a conversation...")
        print("(Or just press Enter to return to menu)")
        
        self.wake_detected = False
        
        cancel_future = asyncio.get_event_loop().run_in_executor(None, input)
        
        try:
            while not self.wake_detected:
                if cancel_future.done():
                    print("↩️  Returning to menu")
                    return
                
                await asyncio.sleep(0.1)
            
            cancel_future.cancel()
            await self.conversation_after_wake_word()
                
        except Exception as e:
            logger.error(f"Wake word error: {e}")
            print(f"❌ Error: {e}")
            if not cancel_future.done():
                cancel_future.cancel()

    async def complete_conversation_workflow(self):
        print("\n" + "🎤 " + "="*48)
        print("COMPLETE VOICE CONVERSATION (NO WAKE WORD)")
        print("="*50)
        
        self.waiting_for_response = True
        self.stt_result = None
        
        try:
            if self.wake_detector:
                self.wake_detector.pause()
                logger.info("⏸️ Pausing wake detector...")
                await asyncio.sleep(1.0)
                logger.info("✅ Microphone ready")
            
            print("\n📍 STEP 1: Recording your voice...")
            print("🎤 Speak now! (Recording for 5 seconds)")
            print("-" * 50)
            
            await self.audio_client.record_for_duration(5.0)
            
            print("✅ Recording complete!")
            
            print("\n📍 STEP 2: Converting speech to text...")
            print("⏳ Processing with OpenAI Whisper...")
            
            timeout = 15
            start_time = asyncio.get_event_loop().time()
            
            while self.stt_result is None:
                await asyncio.sleep(0.1)
                if asyncio.get_event_loop().time() - start_time > timeout:
                    print("❌ Timeout waiting for STT result")
                    return
            
            print(f"✅ You said: '{self.stt_result}'")
            
            print("\n📍 STEP 3: Getting AI response from OpenAI...")
            print("🤖 Processing your question...")
            
            print("\n📍 STEP 4: Receiving and playing AI response...")
            print("🔊 Playing through speakers...")
            print("-" * 50)
            
            await asyncio.sleep(20)
            
            print("-" * 50)
            print("✅ Conversation complete!")
            print("="*50)
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            print(f"❌ Error: {e}")
        finally:
            self.waiting_for_response = False
            
            if self.wake_detector:
                self.wake_detector.resume()
    
    async def _listen_for_audio_responses(self):
        reconnect_delay = 2
        max_reconnect_delay = 30
        
        while self.is_running:
            try:
                while not self.audio_client.websocket and self.is_running:
                    await asyncio.sleep(1)
                
                if not self.is_running:
                    break
                
                try:
                    message = await asyncio.wait_for(
                        self.audio_client.websocket.recv(),
                        timeout=60.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                data = json.loads(message)
                reconnect_delay = 2
                
                message_type = data.get("type")
                
                if message_type == "stt_result":
                    text = data.get("text", "")
                    self.stt_result = text
                    logger.info(f"🎤 STT: '{text}'")
                    
                elif message_type == "stt_processing":
                    logger.info("⏳ Server processing speech...")
                    
                elif message_type == "openai_processing":
                    logger.info("🤖 Getting OpenAI response...")
                    
                elif message_type == "stream_start":
                    logger.info("🔊 Starting audio playback...")
                    
                elif message_type == "response_chunk":
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
                if self.is_running:
                    logger.warning(f"⚠️ Audio listen error: {e}")
                    logger.info(f"🔄 Reconnecting in {reconnect_delay} seconds...")
                    await asyncio.sleep(reconnect_delay)
                    
                    reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
                    
                    try:
                        await self.audio_client.connect()
                    except Exception as conn_err:
                        logger.error(f"Failed to reconnect audio client: {conn_err}")
                else:
                    break


async def main():
    SERVER_URL = "ws://100.88.240.42:8000"
    CLIENT_ID = "rpi_museum_1"
    
    print("="*50)
    print("🔊 Testing espeak-ng...")
    print("="*50)
    
    try:
        import subprocess
        result = subprocess.run(
            ['espeak-ng', '-v', 'en-us', '-s', '160', 'System ready'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✅ espeak-ng working!")
        else:
            print(f"⚠️ espeak-ng returned code {result.returncode}")
    except FileNotFoundError:
        print("❌ espeak-ng not found! Install it:")
        print("   sudo apt-get install espeak-ng")
    except Exception as e:
        print(f"⚠️ espeak-ng test failed: {e}")
    
    print("\n🚀 Starting Museum Client...")
    client = MuseumRPiClient(SERVER_URL, CLIENT_ID)
    await client.start()


if __name__ == "__main__":
    asyncio.run(main())