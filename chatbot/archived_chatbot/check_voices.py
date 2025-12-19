#!/usr/bin/env python3
"""Check available ElevenLabs voices"""
import asyncio
from elevenlabs_voice import ElevenLabsVoice

async def main():
    # Your API key
    api_key = "sk_9f2d335796859839d4daf788a31e5fa7a6eef72d660d010f"
    
    # Create voice component
    voice = ElevenLabsVoice(api_key=api_key)
    
    print("🔍 Fetching available voices from ElevenLabs...\n")
    
    # Get voices
    voices = await voice.get_available_voices()
    
    if voices:
        print(f"✅ Found {len(voices)} voices:\n")
        print("-" * 80)
        
        for v in voices:
            voice_id = v.get("voice_id", "N/A")
            name = v.get("name", "N/A")
            category = v.get("category", "N/A")
            labels = v.get("labels", {})
            description = labels.get("description", "")
            
            # Check if it matches our configured voices
            match = ""
            if voice_id == "EXAVITQu4vr4xnSDxMaL":
                match = " ⭐ (Currently active - Sarah)"
            
            print(f"Name: {name}{match}")
            print(f"ID: {voice_id}")
            print(f"Category: {category}")
            if description:
                print(f"Description: {description}")
            print(f"Labels: {labels}")
            print("-" * 80)
    else:
        print("❌ No voices found")

if __name__ == "__main__":
    asyncio.run(main())
