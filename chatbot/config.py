# config.py - Configuration for OpenAI integration
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AzureOpenAIConfig:
    """Configuration for Azure OpenAI (HKUST) integration"""
    
    # API Configuration
    api_key: str = None
    azure_endpoint: str = "https://hkust.azure-api.net"
    api_version: str = "2024-10-21"
    deployment_name: str = "gpt-4o-mini"  

    max_tokens: int = 120
    temperature: float = 0.7

def load_azure_openai_config():
    """Load Azure OpenAI configuration"""
    
    config = AzureOpenAIConfig(
        api_key=os.getenv("OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://hkust.azure-api.net"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        deployment_name=os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-4o-mini")
    )
    
    if not config.api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    return config

def load_openai_config():
    """Legacy function name - redirects to load_azure_openai_config"""
    return load_azure_openai_config()

@dataclass
class TTSConfig:
    """Configuration for Text-to-Speech"""
    
    # TTS Provider: "google" or "elevenlabs"
    provider: str = "google"
    
    # ElevenLabs settings
    elevenlabs_api_key: str = None
    elevenlabs_voice: str = "rachel"  # Voice name or ID
    elevenlabs_model: str = "eleven_turbo_v2_5"  # Fast model
    elevenlabs_stream: bool = True  # Use streaming for faster response

def load_tts_config():
    """Load TTS configuration"""
    
    config = TTSConfig(
        provider=os.getenv("TTS_PROVIDER", "google").lower(),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY"),
        elevenlabs_voice=os.getenv("ELEVENLABS_VOICE", "rachel"),
        elevenlabs_model=os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5"),
        elevenlabs_stream=os.getenv("ELEVENLABS_STREAM", "true").lower() == "true"
    )
    
    if config.provider == "elevenlabs" and not config.elevenlabs_api_key:
        raise ValueError("ELEVENLABS_API_KEY required when TTS_PROVIDER=elevenlabs")
    
    return config