# esp32_tts_streamer.py - Stream Google TTS audio to ESP32
import asyncio
import logging
import io
from typing import Optional
from fastapi import WebSocket
from pydub import AudioSegment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ESP32TTSStreamer:
    """Stream TTS audio to ESP32 in ESP32-compatible format"""
    
    def __init__(self, voice_component):
        self.voice_component = voice_component
        logger.info("✅ ESP32 TTS Streamer initialized")
    
    async def stream_response_to_esp32(self, text: str, websocket: WebSocket, client_id: str):
        """
        Complete workflow: Text → Google TTS → Convert to ESP32 format → Stream
        
        ESP32 Audio Requirements:
        - Format: WAV
        - Sample Rate: 16kHz (ESP32-friendly)
        - Channels: Mono
        - Bit Depth: 16-bit
        - Streaming: 4KB chunks
        """
        try:
            logger.info(f"🔊 Generating TTS for ESP32 {client_id}: '{text[:50]}...'")
            
            # Step 1: Generate Google TTS (returns MP3)
            mp3_audio = await self.voice_component.create_audio_response_async(text)
            
            if not mp3_audio or len(mp3_audio) < 100:
                logger.error("❌ TTS generation failed")
                await websocket.send_json({
                    "type": "tts_error",
                    "message": "TTS generation failed"
                })
                return
            
            logger.info(f"✅ Generated MP3: {len(mp3_audio)} bytes")
            
            # Step 2: Convert MP3 to ESP32-compatible WAV
            wav_audio = await self._convert_to_esp32_format(mp3_audio)
            
            if not wav_audio:
                logger.error("❌ Audio conversion failed")
                await websocket.send_json({
                    "type": "tts_error",
                    "message": "Audio conversion failed"
                })
                return
            
            logger.info(f"✅ Converted to WAV: {len(wav_audio)} bytes")
            
            # Step 3: Stream to ESP32
            await self._stream_wav_to_esp32(wav_audio, websocket, client_id)
            
            logger.info(f"✅ Streaming complete for {client_id}")
            
        except Exception as e:
            logger.error(f"❌ TTS streaming error: {e}", exc_info=True)
            try:
                await websocket.send_json({
                    "type": "tts_error",
                    "message": str(e)
                })
            except:
                pass
    
    async def _convert_to_esp32_format(self, mp3_bytes: bytes) -> Optional[bytes]:
        """
        Convert MP3 to ESP32-compatible WAV
        - 16kHz sample rate (ESP32 can handle this easily)
        - Mono channel (saves bandwidth)
        - 16-bit PCM (standard)
        """
        try:
            # Load MP3
            audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
            
            # Convert to ESP32 format
            audio = audio.set_frame_rate(16000)  # 16kHz
            audio = audio.set_channels(1)         # Mono
            audio = audio.set_sample_width(2)     # 16-bit
            
            # Export as WAV
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            
            wav_bytes = wav_buffer.getvalue()
            
            logger.info(f"🎵 Audio conversion: {len(mp3_bytes)} bytes MP3 → {len(wav_bytes)} bytes WAV")
            logger.info(f"   Format: 16kHz, Mono, 16-bit")
            
            return wav_bytes
            
        except Exception as e:
            logger.error(f"❌ Audio conversion error: {e}")
            return None
    
    async def _stream_wav_to_esp32(self, wav_bytes: bytes, websocket: WebSocket, client_id: str):
        """
        Stream WAV data to ESP32 in chunks
        
        Protocol:
        1. Send metadata (total size, format info)
        2. Send audio chunks (4KB each)
        3. Send completion signal
        """
        try:
            total_size = len(wav_bytes)
            chunk_size = 4096  # 4KB chunks (good balance for ESP32)
            
            # Step 1: Send metadata
            await websocket.send_json({
                "type": "tts_start",
                "total_bytes": total_size,
                "sample_rate": 16000,
                "channels": 1,
                "bits_per_sample": 16,
                "chunks": (total_size + chunk_size - 1) // chunk_size
            })
            
            logger.info(f"📤 Streaming {total_size} bytes in {chunk_size}-byte chunks")
            
            # Step 2: Stream chunks
            bytes_sent = 0
            chunk_number = 0
            
            while bytes_sent < total_size:
                # Extract chunk
                chunk = wav_bytes[bytes_sent:bytes_sent + chunk_size]
                
                # Send as binary WebSocket message
                await websocket.send_bytes(chunk)
                
                bytes_sent += len(chunk)
                chunk_number += 1
                
                # Log progress every 10 chunks
                if chunk_number % 10 == 0:
                    progress = (bytes_sent / total_size) * 100
                    logger.info(f"📊 Progress: {progress:.1f}% ({bytes_sent}/{total_size} bytes)")
                
                # Small delay to prevent overwhelming ESP32
                await asyncio.sleep(0.005)  # 5ms delay
            
            # Step 3: Send completion signal
            await websocket.send_json({
                "type": "tts_complete",
                "total_bytes": bytes_sent,
                "chunks_sent": chunk_number
            })
            
            logger.info(f"✅ Sent {chunk_number} chunks, {bytes_sent} bytes total")
            
        except Exception as e:
            logger.error(f"❌ Streaming error: {e}")
            raise
    
    async def stream_text_chunks_to_esp32(self, text_stream, websocket: WebSocket, client_id: str):
        """
        Alternative: Stream text chunks and generate TTS per chunk
        Good for very long responses, but increases latency
        """
        accumulated_text = ""
        sentence_buffer = ""
        
        async for text_chunk in text_stream:
            accumulated_text += text_chunk
            sentence_buffer += text_chunk
            
            # Check if we have a complete sentence
            if any(punct in sentence_buffer for punct in ['.', '!', '?']):
                # Generate and stream this sentence
                await self.stream_response_to_esp32(sentence_buffer.strip(), websocket, client_id)
                sentence_buffer = ""
        
        # Stream any remaining text
        if sentence_buffer.strip():
            await self.stream_response_to_esp32(sentence_buffer.strip(), websocket, client_id)


# Integration helper functions
async def stream_openai_response_to_esp32(
    text: str,
    tts_websocket: WebSocket,
    client_id: str,
    voice_component
):
    """
    Helper function: Complete workflow from text to ESP32 audio
    
    Usage in your existing code:
        from esp32_tts_streamer import stream_openai_response_to_esp32
        
        # After getting OpenAI response
        await stream_openai_response_to_esp32(
            text=openai_response,
            tts_websocket=tts_websocket,
            client_id=client_id,
            voice_component=voice_component
        )
    """
    streamer = ESP32TTSStreamer(voice_component)
    await streamer.stream_response_to_esp32(text, tts_websocket, client_id)
                
# Test function
async def test_esp32_streaming():
    """Test ESP32 audio streaming"""
    from optimized_voice import OptimizedVoiceComponent
    
    logger.info("Testing ESP32 TTS Streaming")
    logger.info("=" * 50)
    
    voice = OptimizedVoiceComponent()
    streamer = ESP32TTSStreamer(voice)
    
    test_texts = [
        "Hello! Welcome to Ocean Park!",
        "Red pandas are amazing creatures! They love to climb trees and eat bamboo shoots.",
    ]
    
    for text in test_texts:
        logger.info(f"\nTest: '{text}'")
        
        # Generate MP3
        mp3 = await voice.create_audio_response_async(text)
        if mp3:
            logger.info(f"✅ MP3: {len(mp3)} bytes")
            
            # Convert to ESP32 format
            wav = await streamer._convert_to_esp32_format(mp3)
            if wav:
                logger.info(f"✅ WAV: {len(wav)} bytes (16kHz, Mono, 16-bit)")
                
                # Save test file
                with open(f"test_esp32_{len(text)}.wav", "wb") as f:
                    f.write(wav)
                logger.info(f"💾 Saved test file")
        
    logger.info("\n✅ Test completed!")


if __name__ == "__main__":
    asyncio.run(test_esp32_streaming())