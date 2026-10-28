"""Central settings for the chatbot. Reads from backend/.env."""
import os
from dotenv import load_dotenv

load_dotenv()

# Which AI model runs the chatbot: gemini | groq | openrouter | ollama | anthropic
PROVIDER = os.getenv("CHATBOT_PROVIDER", "gemini").strip().lower()
CHATBOT_MODEL = os.getenv("CHATBOT_MODEL", "").strip()   # empty = the provider's default below

# Defaults only. Free-tier model names change over time: check the provider's current model list if a name is rejected.
DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
    "ollama": "qwen2.5:7b",
    "anthropic": "claude-sonnet-5-5",
}

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv(
    "CHATBOT_EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
VECTOR_DIR = os.getenv("CHATBOT_VECTOR_DIR", "./chatbot_vectorstore")
KB_DIR = os.getenv("CHATBOT_KB_DIR", "./app/chatbot/knowledge")
RATE_LIMIT = os.getenv("CHATBOT_RATE_LIMIT", "20/minute")
KSDMA_DATA_READY = os.getenv("CHATBOT_KSDMA_DATA_READY", "false").strip().lower() == "true"

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
