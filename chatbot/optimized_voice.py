# optimized_voice.py serves two purposes: 1. server side google TTS, 2. 
# optimized_voice.py - GOOGLE TTS VERSION (NO TRUNCATION)
import io
import base64
import os
import time
from typing import Any, Dict, List, Optional
import tempfile
import threading
import asyncio
import concurrent.futures
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google TTS import
try:
    from gtts import gTTS
    import pygame
    HAS_GTTS = True
    logger.info("Google TTS available")
except ImportError as e:
    HAS_GTTS = False
    logger.error(f"Google TTS not available: {e}")
    logger.info("Install with: pip install gtts pygame")

# Speech recognition imports
try:
    import speech_recognition as sr
    import pyaudio
    HAS_SPEECH_RECOGNITION = True
    logger.info("Speech recognition available")
except ImportError as e:
    HAS_SPEECH_RECOGNITION = False
    logger.warning(f"Speech recognition not available: {e}")

try:
    from pydub import AudioSegment
    HAS_PYDUB = True
    logger.info("PyDub available")
except ImportError:
    HAS_PYDUB = False
    logger.warning("PyDub not available")

class OptimizedVoiceComponent:
    """Google TTS voice component - reliable online TTS with FULL response audio"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.audio_settings = self.config.get("audio_settings", {
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 1024
        })
        
        # Thread pool for async operations
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        
        # Initialize pygame mixer for audio playback
        if HAS_GTTS:
            try:
                pygame.mixer.init()
                self.tts_available = True
                logger.info("Google TTS engine ready - FULL response audio enabled")
            except Exception as e:
                logger.error(f"Pygame mixer init failed: {e}")
                self.tts_available = False
        else:
            self.tts_available = False
        
        if HAS_SPEECH_RECOGNITION:
            # Initialize speech recognition
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.5
            logger.info("Voice component ready")
        else:
            self.recognizer = None
            logger.warning("Voice component - speech recognition disabled")

    async def create_audio_response_async(self, text: str) -> Optional[bytes]:
        """Async Google TTS generation - FULL text, no truncation"""
        if not HAS_GTTS or not self.tts_available:
            logger.debug("Google TTS not available")
            return None
        
        if not text or not text.strip():
            return None
        
        # Remove all truncation - use full response text
        logger.info(f"Creating Google TTS for FULL response: {len(text)} chars")
        
        # Run Google TTS in thread pool
        loop = asyncio.get_event_loop()
        try:
            # Use dynamic timeout based on text length (more time for longer text)
            estimated_time = max(15.0, len(text) / 25)  # ~1 second per 100 chars
            timeout = min(60.0, estimated_time)  # Cap at 30 seconds
            
            audio_data = await asyncio.wait_for(
                loop.run_in_executor(
                    self.executor, 
                    self._create_gtts_sync, 
                    text
                ),
                timeout=timeout
            )
            
            if audio_data:
                logger.info(f"Google TTS completed: {len(audio_data)} bytes for {len(text)} chars")
            else:
                logger.warning("Google TTS failed")
                
            return audio_data
            
        except asyncio.TimeoutError:
            logger.warning(f"Google TTS timeout after {timeout}s for {len(text)} chars")
            return None
        except Exception as e:
            logger.error(f"Google TTS error: {e}")
            return None

    def _create_gtts_sync(self, text: str) -> Optional[bytes]:
        """Synchronous Google TTS generation - FULL text"""
        try:
            logger.debug(f"Generating TTS for: '{text[:50]}...' ({len(text)} chars total)")
            
            # Create Google TTS object with full text
            tts = gTTS(text=text, lang='en', slow=False)
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            temp_filename = temp_file.name
            temp_file.close()
            
            try:
                # Generate audio file
                tts.save(temp_filename)
                
                # Read the generated audio file
                if os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 100:
                    with open(temp_filename, 'rb') as audio_file:
                        audio_data = audio_file.read()
                    
                    logger.debug(f"TTS file generated: {len(audio_data)} bytes")
                    return audio_data
                else:
                    logger.warning("Google TTS file not generated properly")
                    return None
                    
            finally:
                # Cleanup temp file
                if os.path.exists(temp_filename):
                    try:
                        os.unlink(temp_filename)
                    except:
                        pass
                    
        except Exception as e:
            logger.error(f"Google TTS generation failed: {e}")
            return None

    def create_audio_response(self, text: str, quick_test: bool = False) -> Optional[bytes]:
        """Synchronous Google TTS for testing"""
        if quick_test:
            text = "Hello! Test message."
        
        return self._create_gtts_sync(text)

    # Speech recognition methods (same as before)
    async def process_audio_to_text_async(self, audio_data: bytes, audio_format: str = "audio/wav") -> str:
        """Async speech recognition"""
        if not HAS_SPEECH_RECOGNITION or not self.recognizer:
            return ""
        
        if len(audio_data) < 500:
            return ""
        
        logger.info(f"Processing audio: {len(audio_data)} bytes")
        
        loop = asyncio.get_event_loop()
        try:
            text = await loop.run_in_executor(
                self.executor, 
                self._process_audio_sync, 
                audio_data, 
                audio_format
            )
            
            if text:
                logger.info(f"Speech recognized: '{text}'")
                
            return text or ""
            
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            return ""

    def _process_audio_sync(self, audio_data: bytes, audio_format: str) -> str:
        """Synchronous speech recognition"""
        temp_filename = None
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_filename = temp_file.name
            
            # Convert audio format if needed
            if self._convert_audio_to_wav(audio_data, audio_format, temp_filename):
                logger.debug("Audio converted to WAV")
            else:
                temp_file.write(audio_data)
            
            temp_file.close()
            
            # Process with speech recognition
            if os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 44:
                with sr.AudioFile(temp_filename) as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio = self.recognizer.record(source, duration=15)
                
                # Try Google recognition first
                try:
                    text = self.recognizer.recognize_google(audio, language="en-US")
                    return text
                except sr.UnknownValueError:
                    logger.debug("Google: Could not understand audio")
                except sr.RequestError as e:
                    logger.debug(f"Google service error: {e}")
                
                # Try Sphinx fallback
                try:
                    text = self.recognizer.recognize_sphinx(audio)
                    return text
                except Exception as e:
                    logger.debug(f"Sphinx error: {e}")
            
            return ""
            
        except Exception as e:
            logger.error(f"Speech recognition failed: {e}")
            return ""
            
        finally:
            if temp_filename and os.path.exists(temp_filename):
                try:
                    os.unlink(temp_filename)
                except:
                    pass

    def _convert_audio_to_wav(self, audio_data: bytes, audio_format: str, output_filename: str) -> bool:
        """Convert audio to WAV format"""
        if not HAS_PYDUB:
            return False
        
        try:
            if "webm" in audio_format.lower():
                format_name = "webm"
            elif "ogg" in audio_format.lower():
                format_name = "ogg"
            elif "mp4" in audio_format.lower() or "m4a" in audio_format.lower():
                format_name = "mp4"
            else:
                format_name = "wav"
            
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format=format_name)
            audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
            audio_segment.export(output_filename, format="wav")
            return True
            
        except Exception as e:
            logger.debug(f"Audio conversion failed: {e}")
            return False

    def process_audio_to_text(self, audio_data: bytes, audio_format: str = "audio/wav") -> str:
        """Sync speech recognition for compatibility"""
        return self._process_audio_sync(audio_data, audio_format)

    def process(self, messages: List[Any]) -> List[Dict[str, Any]]:
        """Process messages for RASA compatibility"""
        processed = []
        for message in messages:
            try:
                audio_data = message.get("audio_data")
                audio_format = message.get("format", "audio/wav")
                
                if audio_data:
                    text = self.process_audio_to_text(audio_data, audio_format)
                    processed.append({"text": text})
                else:
                    processed.append({"text": "No audio data provided"})
            except Exception as e:
                processed.append({"text": f"Processing error: {str(e)}"})
        
        return processed
    
    def test_audio_capabilities(self):
        """Test audio capabilities"""
        logger.info("Testing Google TTS Audio Capabilities (FULL RESPONSE)")
        logger.info("=" * 40)
        
        if self.tts_available:
            logger.info("TTS Engine: Google TTS (online) - FULL text enabled")
            # Test TTS with longer text
            test_text = "Hello! This is Google TTS test. We can now speak full responses without truncation. This means kids will hear the complete story about the artworks!"
            test_audio = self.create_audio_response(test_text, quick_test=False)
            if test_audio and len(test_audio) > 100:
                logger.info(f"TTS Test: SUCCESS - Generated {len(test_audio)} bytes for {len(test_text)} chars")
            else:
                logger.warning("TTS Test: FAILED")
        else:
            logger.info("TTS Engine: Not available")
        
        if self.recognizer:
            logger.info("Speech Recognition: Available")
        else:
            logger.info("Speech Recognition: Not available")
        
        logger.info(f"Audio conversion (PyDub): {'Available' if HAS_PYDUB else 'Not available'}")
        logger.info(f"Audio Settings: {self.audio_settings}")

    def __del__(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'executor') and self.executor:
                self.executor.shutdown(wait=False)
        except:
            pass
        
        try:
            pygame.mixer.quit()
        except:
            pass

# Test function
async def test_google_tts_full_response():
    """Test Google TTS component with full responses"""
    logger.info("Testing Google TTS Component (FULL RESPONSE)")
    logger.info("=" * 40)
    
    voice = OptimizedVoiceComponent()
    voice.test_audio_capabilities()
    
    if voice.tts_available:
        logger.info("Testing Google TTS with full responses...")
        
        test_texts = [
            "Hello! Welcome to our museum!",
            "Van Gogh's 'Cafe Terrace at Night' is a beautiful painting that shows a charming cafe scene under the stars. The artist used bold yellows and deep blues to create a magical nighttime atmosphere. You can find this amazing artwork in our Van Gogh Wing! What do you think about the way he painted the stars?",
            "The story of Lady Jane Grey is both fascinating and tragic. She was known as the Nine Days' Queen because she ruled England for just nine days before being executed. Paul Delaroche's painting captures this sad moment in history with incredible detail and emotion. The artist spent years researching to make it historically accurate. You can see how the light falls dramatically across the scene, creating a sense of both beauty and sadness."
        ]
        
        for i, text in enumerate(test_texts, 1):
            logger.info(f"Test {i}: {len(text)} characters - '{text[:50]}...'")
            start_time = time.time()
            
            audio_result = await voice.create_audio_response_async(text)
            
            end_time = time.time()
            
            if audio_result:
                logger.info(f"SUCCESS: {len(audio_result)} bytes in {end_time - start_time:.2f}s")
                logger.info(f"Audio-to-text ratio: {len(audio_result)/len(text):.1f} bytes per character")
            else:
                logger.warning("FAILED: No audio generated")
        
        logger.info("Google TTS full response test completed!")
    else:
        logger.info("Google TTS not available")

if __name__ == "__main__":
    import asyncio
    
    # Check if dependencies are installed
    if not HAS_GTTS:
        print("Google TTS not available. Install with:")
        print("pip install gtts pygame")
    else:
        asyncio.run(test_google_tts_full_response())