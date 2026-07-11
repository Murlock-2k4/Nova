import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


# Assistant
ASSISTANT_NAME = "Nova"
WAKE_PHRASES = ["nova", "hey nova", "no va", "hey no va"]
ACTIVE_TIMEOUT = 8


# Local AI
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_KEEP_ALIVE = "30m"


# Location
TIMEZONE = os.getenv("NOVA_TIMEZONE", "America/Denver")
HOME_CITY = os.getenv("NOVA_HOME_CITY", "Denver")


# Speech recognition
VOSK_MODEL_PATH = BASE_DIR / "vosk-model-small-en-us-0.15"
MIC_DEVICE = 1
MIC_SAMPLE_RATE = 48000
MIC_BLOCK_SIZE = 8000


# Text-to-speech
PIPER_MODEL_PATH = BASE_DIR / "en_US-amy-medium.onnx"
PIPER_OUTPUT_FILE = BASE_DIR / "nova_output.wav"


# Local data
ALARMS_FILE = BASE_DIR / "alarms.json"
GOOGLE_TOKEN_FILE = BASE_DIR / "token.json"
GOOGLE_CREDENTIALS_FILE = BASE_DIR / "credentials.json"


# Spotify
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
SPOTIFY_SCOPE = (
    "user-read-playback-state "
    "user-modify-playback-state"
)

# Logging
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "nova.log"
LOG_LEVEL = os.getenv("NOVA_LOG_LEVEL", "INFO").upper()