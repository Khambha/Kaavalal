"""Layer 1: instant, rule-based emergency handling. No LLM involved.

Two jobs only:
  1. a clear cry for help ("I am trapped", "water is rising", "രക്ഷിക്കൂ") -> 112 + official numbers, immediately;
  2. a GENERIC request for the helpline ("emergency number", "helpline") -> the official numbers.
Anything more specific ("taluk emergency number Vadakara", "hospital phone number", "can you help me find a shelter")
is NOT answered here: it goes to the agent, which has the tools to answer it properly.
"""
import re
from .config import EMERGENCY_CONTACTS, normalize_district

# Clear danger: always answered here, whatever else the message says.
_STRONG_RE = re.compile("|".join([
    r"\btrapped\b", r"\bdrown(ing|ed)?\b", r"\bsave me\b", r"\bsos\b", r"\bwater (is )?rising\b",
    r"\bcan'?t (get out|escape)\b", r"\blandslide (just )?(hit|happened)\b",
    r"\bsomeone is (dying|injured|unconscious)\b",
    r"രക്ഷിക്ക", r"മുങ്ങ", r"കുടുങ്ങി",
]), re.IGNORECASE)

# A bare "help" is only treated as an emergency when it is the whole message (<= 4 words),
# so "can you help me find a shelter in Wayanad?" still reaches the agent.
_WEAK_RE = re.compile(r"\bhelp( me| us)?\b|സഹായിക്ക", re.IGNORECASE)

# Generic helpline request.
_HELPLINE_RE = re.compile(
    r"\b(helplines?|emergency (numbers?|contacts?|phone)|control room)\b|ഹെൽപ്പ്\s*ലൈൻ|അടിയന്തര\s*(നമ്പർ|നമ്പറുകൾ|ഫോൺ)",
    re.IGNORECASE)

# Words that mean the person wants something specific that a tool can look up.
_SPECIFIC_RE = re.compile(
    r"\b(taluk|taluka|hospitals?|camps?|shelters?|kiosks?|collector|panchayat|village|office|clinic|"
    r"doctor|alert|risk|rain|rainfall|incident)\b|താലൂക്ക്|ആശുപത്രി|ക്യാമ്പ്|പഞ്ചായത്ത്|വില്ലേജ്",
    re.IGNORECASE)


def _contacts_text() -> str:
    return "\n".join(f"- {k}: {v}" for k, v in EMERGENCY_CONTACTS.items())


def _is_emergency(text: str) -> bool:
    if _STRONG_RE.search(text):
        return True
    return bool(_WEAK_RE.search(text)) and len(text.split()) <= 4 and not _SPECIFIC_RE.search(text)


def check(text: str, language: str = "en"):
    """Return a reply dict if the message needs a fixed answer, else None (the agent will handle it)."""
    if _is_emergency(text):
        if language == "ml":
            body = ("ഇത് അടിയന്തര സാഹചര്യമാണെങ്കിൽ ഉടൻ 112 ൽ വിളിക്കുക.\n"
                    "സുരക്ഷിതമായ ഉയർന്ന സ്ഥലത്തേക്ക് മാറുക.\n\n" + _contacts_text())
        else:
            body = ("If you are in immediate danger, call 112 now.\n"
                    "Move to higher, safe ground if you can.\n\n" + _contacts_text())
        return {"reply": body, "layer": "rules", "emergency": True}

    if _HELPLINE_RE.search(text) and not _SPECIFIC_RE.search(text) and not normalize_district(text):
        head = "അടിയന്തര നമ്പറുകൾ:" if language == "ml" else "Emergency contacts:"
        return {"reply": f"{head}\n{_contacts_text()}", "layer": "rules", "emergency": False}
    return None
