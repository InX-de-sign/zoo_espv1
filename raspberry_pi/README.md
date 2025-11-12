# Museum AI - Raspberry Pi Client

## Installation
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y espeak python3-pyaudio portaudio19-dev python3-pip

# Install Python packages
pip3 install -r requirements.txt
```

## Configuration

Edit `main_client.py` and update the server URL:
```python
SERVER_URL = "ws://YOUR_PC_IP:8000"
```

## Run
```bash
python3 main_client.py
```