#!/usr/bin/env python3
# diagnostic.py - Check system components
import subprocess
import sys
import socket

print("="*60)
print("🔍 RASPBERRY PI AUDIO SYSTEM DIAGNOSTIC")
print("="*60)

# 1. Check Python version
print("\n1️⃣ Python Version:")
print(f"   {sys.version}")

# 2. Check espeak-ng
print("\n2️⃣ Testing espeak-ng...")
try:
    result = subprocess.run(
        ['espeak-ng', '--version'],
        capture_output=True,
        text=True,
        timeout=5
    )
    print(f"   ✅ espeak-ng installed: {result.stdout.split()[1] if result.stdout else 'unknown version'}")
    
    # Test speech
    subprocess.run(['espeak-ng', 'Testing audio output'], timeout=5)
    print("   ✅ espeak-ng audio test complete")
except FileNotFoundError:
    print("   ❌ espeak-ng NOT FOUND")
    print("   Install: sudo apt-get install espeak-ng")
except Exception as e:
    print(f"   ❌ espeak-ng error: {e}")

# 3. Check required Python packages
print("\n3️⃣ Checking Python packages...")
packages = ['pyaudio', 'websockets', 'asyncio']
for pkg in packages:
    try:
        __import__(pkg)
        print(f"   ✅ {pkg}")
    except ImportError:
        print(f"   ❌ {pkg} NOT INSTALLED")
        if pkg == 'pyaudio':
            print("      Install: sudo apt-get install portaudio19-dev python3-pyaudio")
        else:
            print(f"      Install: pip3 install {pkg}")

# 4. Check audio devices
print("\n4️⃣ Audio Devices:")
try:
    import pyaudio
    p = pyaudio.PyAudio()
    
    # Input devices
    print("   Input devices:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f"      - {info['name']} (channels: {info['maxInputChannels']})")
    
    # Output devices
    print("   Output devices:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxOutputChannels'] > 0:
            print(f"      - {info['name']} (channels: {info['maxOutputChannels']})")
    
    p.terminate()
    print("   ✅ Audio devices detected")
except Exception as e:
    print(f"   ❌ Error checking audio: {e}")

# 5. Test microphone recording
print("\n5️⃣ Testing microphone recording...")
try:
    import pyaudio
    import wave
    
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    RECORD_SECONDS = 2
    
    p = pyaudio.PyAudio()
    
    print("   🎤 Recording 2 seconds...")
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    
    frames = []
    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # Save test file
    wf = wave.open('test_recording.wav', 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
    print("   ✅ Recording successful (saved as test_recording.wav)")
    print("   Play with: aplay test_recording.wav")
    
except Exception as e:
    print(f"   ❌ Recording failed: {e}")

# 6. Check network connectivity
print("\n6️⃣ Network Check:")
SERVER_IP = "100.88.240.42"  # Change to your server IP
SERVER_PORT = 8000

print(f"   Testing connection to {SERVER_IP}:{SERVER_PORT}...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex((SERVER_IP, SERVER_PORT))
    sock.close()
    
    if result == 0:
        print(f"   ✅ Server is reachable at {SERVER_IP}:{SERVER_PORT}")
    else:
        print(f"   ❌ Cannot connect to server")
        print(f"      Error code: {result}")
except Exception as e:
    print(f"   ❌ Network error: {e}")

# 7. Test WebSocket connection
print("\n7️⃣ Testing WebSocket connection...")
try:
    import asyncio
    import websockets
    
    async def test_ws():
        try:
            uri = f"ws://{SERVER_IP}:{SERVER_PORT}/ws/audio"
            print(f"   Connecting to {uri}...")
            async with websockets.connect(uri, timeout=5) as ws:
                print("   ✅ WebSocket connection successful")
                
                # Send test message
                await ws.send('{"type":"test"}')
                print("   ✅ Can send messages")
                return True
        except Exception as e:
            print(f"   ❌ WebSocket failed: {e}")
            return False
    
    result = asyncio.run(test_ws())
    
except Exception as e:
    print(f"   ❌ WebSocket test error: {e}")

# 8. File system check
print("\n8️⃣ File System:")
import os
try:
    # Check if audioInput folder can be created
    os.makedirs("audioInput", exist_ok=True)
    print("   ✅ Can create audioInput folder")
    
    # Check write permissions
    test_file = "audioInput/test.txt"
    with open(test_file, 'w') as f:
        f.write("test")
    os.remove(test_file)
    print("   ✅ Can write to audioInput folder")
    
except Exception as e:
    print(f"   ❌ File system error: {e}")

print("\n" + "="*60)
print("🏁 DIAGNOSTIC COMPLETE")
print("="*60)
print("\nIf any checks failed, address them before running the client.")
print("Update SERVER_IP in this script and main_client.py to match your server.")