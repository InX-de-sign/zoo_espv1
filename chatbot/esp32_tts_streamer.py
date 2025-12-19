# esp32_tts_streamer.py - Stream Google TTS audio to ESP32
import asyncio
import logging
import io
import wave
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
    
    async def stream_mp3_to_esp32(self, text: str, websocket: WebSocket, client_id: str):
        """
        ⚡ FASTEST: Stream MP3 directly as Edge TTS generates (NO CONVERSION!)
        """
        try:
            logger.info(f"🚀 STREAMING MP3 to ESP32 {client_id}: '{text[:50]}...'")
            
            # Send stream start notification
            await websocket.send_json({
                "type": "tts_start",
                "format": "mp3",
                "text_length": len(text)
            })
            
            total_bytes = 0
            chunk_count = 0
            
            # Stream MP3 chunks as they generate
            async for mp3_chunk in self.voice_component.stream_edge_tts_mp3(text):
                await websocket.send_bytes(mp3_chunk)
                total_bytes += len(mp3_chunk)
                chunk_count += 1
                
                # Minimal delay for flow control (1ms instead of 10ms)
                await asyncio.sleep(0.001)
            
            # Send completion signal
            await websocket.send_json({
                "type": "tts_complete",
                "total_bytes": total_bytes,
                "chunks_sent": chunk_count
            })
            
            logger.info(f"✅ Streamed {chunk_count} MP3 chunks, {total_bytes} bytes")
            
        except Exception as e:
            logger.error(f"❌ MP3 streaming error: {e}", exc_info=True)
            raise
    
    async def stream_response_to_esp32(self, text: str, websocket: WebSocket, client_id: str):
        """
        Stream audio in real-time as it's being generated
        """
        try:
            logger.info(f"🔊 Generating TTS for ESP32 {client_id}: '{text[:50]}...'")
            
            # Step 1: Start TTS generation
            mp3_audio = await self.voice_component.create_audio_response_async(text)
            
            if not mp3_audio or len(mp3_audio) < 100:
                logger.error("❌ TTS generation failed")
                return
            
            logger.info(f"✅ Generated MP3: {len(mp3_audio)} bytes")
            
            # Step 2: Convert to WAV
            audio = AudioSegment.from_mp3(io.BytesIO(mp3_audio))
            audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            audio = audio.speedup(playback_speed=1.2)
            
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            wav_bytes = wav_buffer.getvalue()
            
            # Step 3: Stream and WAIT for completion
            await self._stream_wav_to_esp32(wav_bytes, websocket, client_id)
            
            logger.info(f"✅ Streaming started for {client_id}")
            
        except Exception as e:
            logger.error(f"❌ TTS streaming error: {e}", exc_info=True)

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

            # ElevenLabs optimization: Lower sample rate for smaller files
            audio = audio.set_frame_rate(8000)   # 8kHz saves bandwidth (still clear for speech)
            audio = audio.set_channels(1)        # Mono
            audio = audio.set_sample_width(2)    # 16-bit
            
            # Optional speedup (configurable via AUDIO_SPEED env var)
            import os
            speed = float(os.getenv('AUDIO_SPEED', '1.0'))
            if speed != 1.0:
                audio = audio.speedup(playback_speed=speed)
                logger.info(f"   Speed: {speed}x")
            
            # Export as WAV
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            
            wav_bytes = wav_buffer.getvalue()
            
            logger.info(f"🎵 Audio conversion: {len(mp3_bytes)} bytes MP3 → {len(wav_bytes)} bytes WAV")
            logger.info(f"   Format: 8kHz, Mono, 16-bit (optimized for ESP32)")
            
            return wav_bytes
            
        except Exception as e:
            logger.error(f"❌ Audio conversion error: {e}")
            return None
    
    async def _stream_wav_to_esp32(self, wav_bytes: bytes, websocket: WebSocket, client_id: str):
        """Stream WAV audio to ESP32 in chunks with optimized flow control"""
        try:
            # Parse WAV to get audio parameters
            wav_io = io.BytesIO(wav_bytes)
            with wave.open(wav_io, 'rb') as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                bits_per_sample = wf.getsampwidth() * 8
                total_bytes = len(wav_bytes)
            
            chunk_size = 8192  # ⚡ Increased from 4096 to 8192
            num_chunks = (total_bytes + chunk_size - 1) // chunk_size
            
            # Send stream start notification
            await websocket.send_json({
                "type": "tts_start",
                "total_bytes": total_bytes,
                "sample_rate": sample_rate,
                "channels": channels,
                "bits_per_sample": bits_per_sample,
                "chunks": num_chunks
            })
            
            logger.info(f"📤 Streaming {total_bytes} bytes in {chunk_size}-byte chunks")
            
            # Stream chunks with minimal delay
            for i in range(0, total_bytes, chunk_size):
                chunk = wav_bytes[i:i + chunk_size]
                await websocket.send_bytes(chunk)
                
                if (i + chunk_size) % 40960 == 0:  # Log every ~40KB
                    progress = ((i + chunk_size) * 100.0) / total_bytes
                    logger.info(f"📊 Progress: {progress:.1f}% ({i + chunk_size}/{total_bytes} bytes)")
                
                # ⚡ Reduced from 0.01 to 0.001 (10x faster!)
                await asyncio.sleep(0.001)
            
            await asyncio.sleep(0.01)

            await websocket.send_json({
                "type": "tts_complete",
                "total_bytes": total_bytes,
                "chunks_sent": num_chunks
            })
            
            logger.info(f"✅ Sent {num_chunks} chunks, {total_bytes} bytes total")
            
        except Exception as e:
            logger.error(f"❌ Streaming error: {e}", exc_info=True)
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