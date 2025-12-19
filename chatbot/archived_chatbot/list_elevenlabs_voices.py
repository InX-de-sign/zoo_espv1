#!/usr/bin/env python3
"""List all available ElevenLabs voices with their IDs"""
import asyncio
import os
from elevenlabs_voice import ElevenLabsVoice

async def list_voices():
    # Read API key from .env
    api_key = None
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('ELEVENLABS_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
                    break
    except:
        pass
    
    if not api_key:
        print("❌ No ELEVENLABS_API_KEY found in .env")
        return
    
    # Create voice component
    voice = ElevenLabsVoice(api_key=api_key)
    
    # Fetch voices
    print("🔍 Fetching available voices from ElevenLabs...\n")
    voices = await voice.get_available_voices()
    
    if not voices:
        print("❌ No voices found")
        return
    
    print(f"✅ Found {len(voices)} voices:\n")
    print("=" * 80)
    
    # Look for Sarah voices
    sarah_voices = []
    
    for v in voices:
        name = v.get('name', 'Unknown')
        voice_id = v.get('voice_id', 'Unknown')
        category = v.get('category', 'Unknown')
        description = v.get('description', 'No description')
        labels = v.get('labels', {})
        
        # Check if it's a Sarah voice
        if 'sarah' in name.lower():
            sarah_voices.append(v)
        
        print(f"Name: {name}")
        print(f"ID: {voice_id}")
        print(f"Category: {category}")
        print(f"Description: {description[:100]}...")
        if labels:
            print(f"Labels: {labels}")
        print("-" * 80)
    
    # Highlight Sarah voices
    if sarah_voices:
        print("\n🎯 SARAH VOICES FOUND:")
        print("=" * 80)
        for v in sarah_voices:
            print(f"\nName: {v.get('name')}")
            print(f"Voice ID: {v.get('voice_id')}")
            print(f"Description: {v.get('description', 'No description')}")
            print(f"\nTo use this voice, set in .env:")
            print(f"ELEVENLABS_VOICE_ID={v.get('voice_id')}")
            print("-" * 80)

if __name__ == "__main__":
    asyncio.run(list_voices())
