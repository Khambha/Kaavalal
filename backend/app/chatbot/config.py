"""Central settings for the chatbot. Reads from backend/.env."""
from pathlib import Path
from app.core.config import BASE_DIR, settings as app_settings


def _backend_path(configured_value: str) -> str:
    """Resolve chatbot paths from the backend directory, independent of process cwd."""
    configured = Path(configured_value).expanduser()
    return str(configured if configured.is_absolute() else (BASE_DIR / configured).resolve())

# Which AI model runs the chatbot: gemini | groq | openrouter | ollama | anthropic
PROVIDER = app_settings.CHATBOT_PROVIDER.strip().lower()
CHATBOT_MODEL = app_settings.CHATBOT_MODEL.strip()   # empty = the provider's default below

# Defaults only. Free-tier model names change over time: check the provider's current model list if a name is rejected.
DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
    "ollama": "qwen2.5:7b",
    "anthropic": "claude-sonnet-5-5",
}

ANTHROPIC_API_KEY = app_settings.ANTHROPIC_API_KEY or ""
GOOGLE_API_KEY = app_settings.GOOGLE_API_KEY or ""
GROQ_API_KEY = app_settings.GROQ_API_KEY or ""
OPENROUTER_API_KEY = app_settings.OPENROUTER_API_KEY or ""
OLLAMA_BASE_URL = app_settings.OLLAMA_BASE_URL
EMBEDDING_MODEL = app_settings.CHATBOT_EMBEDDING_MODEL
VECTOR_DIR = _backend_path(app_settings.CHATBOT_VECTOR_DIR)
KB_DIR = _backend_path(app_settings.CHATBOT_KB_DIR)
RATE_LIMIT = app_settings.CHATBOT_RATE_LIMIT
KSDMA_DATA_READY = app_settings.CHATBOT_KSDMA_DATA_READY

# Chatbot identity (change here to rename it everywhere in the backend)
BOT_NAME = "Thunai"
BOT_NAME_ML = "തുണ"

# Kerala's 14 districts: canonical English name -> aliases (lowercase English + Malayalam)
KERALA_DISTRICTS = {
    "Thiruvananthapuram": ["trivandrum", "തിരുവനന്തപുരം"],
    "Kollam": ["quilon", "കൊല്ലം"],
    "Pathanamthitta": ["പത്തനംതിട്ട"],
    "Alappuzha": ["alleppey", "ആലപ്പുഴ"],
    "Kottayam": ["കോട്ടയം"],
    "Idukki": ["ഇടുക്കി"],
    "Ernakulam": ["kochi", "cochin", "എറണാകുളം", "കൊച്ചി"],
    "Thrissur": ["trichur", "തൃശ്ശൂർ", "തൃശൂർ"],
    "Palakkad": ["palghat", "പാലക്കാട്"],
    "Malappuram": ["മലപ്പുറം"],
    "Kozhikode": ["calicut", "കോഴിക്കോട്"],
    "Wayanad": ["വയനാട്"],
    "Kannur": ["cannanore", "കണ്ണൂർ"],
    "Kasaragod": ["kasargod", "കാസർഗോഡ്", "കാസർകോട്"],
}


def normalize_district(text: str):
    """Return the canonical Kerala district name found in `text`, or None."""
    if not text:
        return None
    t = text.lower()
    for name, aliases in KERALA_DISTRICTS.items():
        if name.lower() in t or any(a in t for a in aliases):
            return name
    return None


MAX_MESSAGE_CHARS = 1000
HISTORY_TURNS = 6

# Official numbers live here, never in LLM output.
EMERGENCY_CONTACTS = {
    "National emergency": "112",
    "KSDMA State Control Room": "1070",
    "District emergency (toll free)": "1077",
    "Police": "100",
    "Fire & Rescue": "101",
    "Ambulance": "108",
}
