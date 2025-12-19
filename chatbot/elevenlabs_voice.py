# elevenlabs_voice.py - ElevenLabs TTS Integration
import io
import asyncio
import logging
from typing import Optional, Dict, Any
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ElevenLabsVoice:
    """ElevenLabs Text-to-Speech component with streaming support"""
    
    # Available voices
    VOICES = {
        "rachel": "21m00Tcm4TlvDq8ikWAM",  # Calm, clear American female
        "drew": "29vD33N1CtxCmqQRPOHJ",     # Well-rounded American male
        "clyde": "2EiwWnXFnvU5JabPnv8n",    # War veteran American male
        "paul": "5Q0t7uMcjvnagumLfvZi",     # Authoritative American male
        "domi": "AZnzlk1XvdvUeBnXmlld",     # Strong American female
        "dave": "CYw3kZ02Hs0563khs1Fj",     # Young British male
        "fin": "D38z5RcWu1voky8WS1ja",      # Irish male
        "sarah": "emSmWzY0c0xtx5IFMCVv",    # Young, fun, cute (NEW - Fun, Open-minded and Youthful)
        "sarah_mature": "EXAVITQu4vr4xnSDxMaL",  # Mature, reassuring Sarah
        "antoni": "ErXwobaYiN019PkySvjV",   # Well-rounded American male
        "thomas": "GBv7mTt0atIp3BR8iCZE",   # Calm American male
        "charlie": "IKne3meq5aSn9XLyUdCD",  # Casual Australian male
        "george": "JBFqnCBsd6RMkjVDRZzb",   # Warm British male
        "emily": "LcfcDJNUP1GQjkzn1xUU",    # Calm American female
        "elli": "MF3mGyEYCl7XYWbV9V6O",     # Emotional American female
        "callum": "N2lVS1w4EtoT3dr4eOWO",   # Intense American male
        "patrick": "ODq5zmih8GrVes37Dizd",  # Shouty American male
        "harry": "SOYHLrjzK2X1ezoPC6cr",    # Anxious American male
        "liam": "TX3LPaxmHKxFdv7VOQHJ",     # Articulate American male
        "dorothy": "ThT5KcBeYPX3keUQqHPh",  # Pleasant British female
    }
    
    def __init__(self, api_key: str, voice: str = "rachel", model: str = "eleven_turbo_v2_5"):
        """
        Initialize ElevenLabs TTS
        
        Args:
            api_key: Your ElevenLabs API key
            voice: Voice ID or name from VOICES dict (default: "rachel")
            model: Model to use (default: "eleven_turbo_v2_5" for speed)
                   Options: "eleven_multilingual_v2", "eleven_turbo_v2_5", "eleven_monolingual_v1"
        """
        self.api_key = api_key
        self.model = model
        
        # Resolve voice name to ID
        if voice in self.VOICES:
            self.voice_id = self.VOICES[voice]
            logger.info(f"✅ Using ElevenLabs voice: {voice} ({self.voice_id})")
        else:
            # Assume it's already a voice ID
            self.voice_id = voice
            logger.info(f"✅ Using ElevenLabs voice ID: {self.voice_id}")
        
        self.base_url = "https://api.elevenlabs.io/v1"
        
    async def create_audio_response_async(self, text: str, stream: bool = False) -> Optional[bytes]:
        """
        Generate audio from text using ElevenLabs API
        
        Args:
            text: Text to convert to speech
            stream: Whether to use streaming (True) or full generation (False)
        
        Returns:
            Audio data as bytes (MP3 format)
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to ElevenLabs TTS")
            return None
        
        try:
            logger.info(f"🎙️ ElevenLabs: Generating TTS for '{text[:80]}...' ({len(text)} chars)")
            
            if stream:
                return await self._stream_audio(text)
            else:
                return await self._generate_audio(text)
                
        except Exception as e:
            logger.error(f"❌ ElevenLabs TTS error: {e}", exc_info=True)
            return None
    
    async def _generate_audio(self, text: str) -> Optional[bytes]:
        """Non-streaming audio generation"""
        url = f"{self.base_url}/text-to-speech/{self.voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                audio_data = response.content
                logger.info(f"✅ ElevenLabs TTS: {len(audio_data)} bytes generated")
                return audio_data
            else:
                logger.error(f"❌ ElevenLabs API error {response.status_code}: {response.text}")
                return None
    
    async def _stream_audio(self, text: str) -> Optional[bytes]:
        """Streaming audio generation (faster time-to-first-byte)"""
        url = f"{self.base_url}/text-to-speech/{self.voice_id}/stream"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }
        
        audio_chunks = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, json=data, headers=headers) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"❌ ElevenLabs stream error {response.status_code}: {error_text}")
                    return None
                
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if chunk:
                        audio_chunks.append(chunk)
        
        if audio_chunks:
            audio_data = b''.join(audio_chunks)
            logger.info(f"✅ ElevenLabs TTS streamed: {len(audio_data)} bytes")
            return audio_data
        
        return None
    
    async def get_available_voices(self) -> list:
        """Get list of available voices from ElevenLabs API"""
        url = f"{self.base_url}/voices"
        headers = {"xi-api-key": self.api_key}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                voices = data.get("voices", [])
                logger.info(f"✅ Found {len(voices)} ElevenLabs voices")
                return voices
            else:
                logger.error(f"❌ Failed to get voices: {response.status_code}")
                return []
