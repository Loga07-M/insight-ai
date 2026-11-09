"""Central configuration. Secrets come only from environment variables / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# override=False: real environment variables win; we never modify the .env file.
load_dotenv(BASE_DIR / ".env", override=False)

DB_PATH = Path(os.getenv("INSIGHT_DB_PATH", BASE_DIR / "data" / "insight.db"))

# ---- Gnani (speech only) ----
GNANI_STT_URL = "https://api.vachana.ai/stt/v3"
GNANI_TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"
GNANI_STT_MODEL_LABEL = "Prisma v2.5"   # default model when `model` is omitted
GNANI_TTS_MODEL = "timbre-v2.5"
STT_MAX_SECONDS = 30                    # per official REST docs
HTTP_TIMEOUT = 60


def gnani_key() -> str:
    return os.getenv("GNANI_API_KEY", "").strip()


# ---- LLM (reasoning) ----
def llm_settings() -> dict:
    return {
        "provider": os.getenv("LLM_PROVIDER", "openai_compatible").strip().lower(),
        "api_key": os.getenv("LLM_API_KEY", "").strip(),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/"),
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini").strip(),
    }


def redact(text: str) -> str:
    """Remove any configured secret from a string before it is shown or logged."""
    text = str(text)
    for secret in (gnani_key(), llm_settings()["api_key"]):
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


INTERESTS = [
    "Artificial Intelligence", "Technology", "Business", "Startups", "Science", "Space",
    "Finance", "Education", "Sports", "Environment", "World affairs", "Health innovation",
]

# Gnani languages (STT + TTS share these codes)
LANGUAGES = {
    "English": "en-IN", "Hindi": "hi-IN", "Tamil": "ta-IN", "Telugu": "te-IN",
    "Kannada": "kn-IN", "Malayalam": "ml-IN", "Marathi": "mr-IN", "Bengali": "bn-IN",
    "Gujarati": "gu-IN", "Punjabi": "pa-IN",
}

# Timbre v2.5 voices by preferred language (official voice catalog).
TTS_VOICES = {
    "en-IN": ["Kaveri", "Trupti", "Devika", "Pranav", "Shlok", "Girish"],
    "hi-IN": ["Nalini", "Bhavna", "Yashvi", "Urmila", "Jwala", "Chitra", "Ambuja",
              "Deepak", "Roopesh", "Vikrant", "Hemraj", "Jalaj", "Omkar"],
    "ta-IN": ["Asmita", "Trisha", "Brinda", "Vedika", "Noopur"],
    "te-IN": ["Suhana", "Lehara", "Lavanya", "Yukti", "Varuni"],
    "kn-IN": ["Saanvi", "Kavin"],
    "ml-IN": ["Reshma", "Riyaan"],
    "mr-IN": ["Zahira", "Ishaan"],
    "bn-IN": ["Kirra", "Dhruva"],
    "gu-IN": ["Falak", "Veera"],
    "pa-IN": ["Mehuli", "Zayan"],
}
