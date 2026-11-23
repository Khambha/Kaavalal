"""Orchestrator: rules first, then the agent. Logs every exchange."""
import logging
import re
import time
import uuid
from sqlalchemy.orm import Session
from . import safety, config
from .request_context import current_user_id, current_location
from .geo import in_kerala_box
from .models import ChatSession, ChatMessage

log = logging.getLogger("thunai")

FALLBACK = {
    "en": "Thunai's AI service is temporarily unavailable, so I can't look up current information right now. For immediate danger call 112; for district disaster assistance call 1077. Check official KSDMA/IMD updates for current alerts.",
    "ml": "തുണയുടെ AI സേവനം താൽക്കാലികമായി ലഭ്യമല്ല; അതിനാൽ ഇപ്പോഴത്തെ വിവരങ്ങൾ പരിശോധിക്കാൻ കഴിയില്ല. അടിയന്തര അപകടത്തിൽ 112-ലും ജില്ലാ ദുരന്തസഹായത്തിന് 1077-ലും വിളിക്കുക. പുതിയ മുന്നറിയിപ്പുകൾ KSDMA/IMD-യിൽ പരിശോധിക്കുക.",
}
QUICK_REPLIES = {
    "en": ["Nearest relief camp", "Water kiosk near me", "Hospitals in my district", "Flood risk today"],
    "ml": ["അടുത്തുള്ള ദുരിതാശ്വാസ ക്യാമ്പ്", "അടുത്തുള്ള കുടിവെള്ള കിയോസ്ക്", "ജില്ലയിലെ ആശുപത്രികൾ", "ഇന്നത്തെ വെള്ളപ്പൊക്ക സാധ്യത"],
}

_RISK_QUESTION_RE = re.compile(
    r"\b(risk|danger level|likelihood)\b|അപകടസാധ്യത|സാധ്യത",
    re.IGNORECASE,
)


def _quick_risk_answer(db: Session, text: str, language: str, context=None):
    """Answer short risk questions from the live risk engine without the LLM agent."""
    if len(text.split()) > 12 or not _RISK_QUESTION_RE.search(text):
        return None

    hazards = (
        (r"\b(flood|flooding)\b|വെള്ളപ്പൊക്കം", "flood"),
        (r"\b(landslide|landslip)\b|ഉരുൾപൊട്ടൽ|മണ്ണിടിച്ചിൽ", "landslide"),
        (r"\b(drought)\b|വരൾച്ച", "drought"),
    )
    selected = next((hazard for pattern, hazard in hazards if re.search(pattern, text, re.IGNORECASE)), "")
    district = config.normalize_district(text)
    if not district and context:
        district = config.normalize_district(context.get("district"))

    if not district:
        return "ഏത് ജില്ലയുടെ അപകടസാധ്യതയാണ് അറിയേണ്ടത്?" if language == "ml" else "Which Kerala district should I check?"

    try:
        from .tools import get_district_risk
        # This fast path uses the exact live-weather tool available to the agent;
        # it must never fall back to legacy stored scores that aren't validated.
        return get_district_risk.invoke({"district": district, "hazard": selected, "language": language})
    except Exception:
        log.exception("Thunai live risk lookup failed for district=%s", district)
        return (
            f"ഇപ്പോൾ {district} ജില്ലയിലെ തത്സമയ കാലാവസ്ഥ/റിസ്ക് വിവരങ്ങൾ ലഭ്യമല്ല. ഔദ്യോഗിക മുന്നറിയിപ്പുകൾ KSDMA/IMD-യിൽ പരിശോധിക്കുക."
            if language == "ml" else
            f"Live weather/risk data for {district} is unavailable right now. Check official KSDMA/IMD alerts; I won't infer a risk level."
        )


def _history(db: Session, session_id: str):
    rows = (db.query(ChatMessage).filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.desc()).limit(config.HISTORY_TURNS).all())
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


def _location(context):
    """(lat, lng) if the user shared a location that is inside Kerala, else None."""
    try:
        lat, lng = context.get("lat"), context.get("lng")
        if lat is not None and lng is not None and in_kerala_box(lat, lng):
            return (round(lat, 4), round(lng, 4))
    except Exception:
        pass
    return None


def _run_agent(history, text: str, language: str, context=None):
    """Returns (reply_text, names_of_tools_used)."""
    from .agent import get_agent
    hints = ["Reply in Malayalam." if language == "ml" else "Reply in English."]
    district = config.normalize_district(context.get("district")) if context else None
    if district:
        hints.append(f"The user is viewing the Kaavalal dashboard for {district} district.")
    if context and context.get("page") == "responder":
        hints.append("The user is using the Kaavalal responder operations module. Provide concise operational guidance; never expose citizen private data or claim to perform an action.")
    if _location(context):
        hints.append("The user has shared their location: for nearest camps or water kiosks call the tool with near_me=true.")
    messages = history + [{"role": "user", "content": f"{text}\n\n({' '.join(hints)})"}]
    result = get_agent().invoke({"messages": messages})
    content = result["messages"][-1].content
    if isinstance(content, list):  # content blocks
        content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
    used = []
    for m in result["messages"]:
        name = getattr(m, "name", None)
        if getattr(m, "type", "") == "tool" and name and name not in used:
            used.append(name)
    return content.strip(), used


def handle_message(db: Session, session_id, text: str, language: str, context=None, user_id=None):
    started_at = time.perf_counter()
    existing = db.get(ChatSession, session_id) if session_id else None
    # Keep anonymous and authenticated conversation histories separate, and never
    # continue another account's conversation when a browser's stored session id remains.
    if existing is not None and existing.user_id != user_id:
        existing, session_id = None, None
    if existing is None:
        session_id = session_id or str(uuid.uuid4())
        if db.get(ChatSession, session_id) is not None:  # id taken by another session
            session_id = str(uuid.uuid4())
        db.add(ChatSession(id=session_id, user_id=user_id, language=language))
        db.commit()
    history = _history(db, session_id)
    db.add(ChatMessage(session_id=session_id, role="user", content=text))
    db.commit()

    fixed = safety.check(text, language)
    if fixed:
        reply, layer, emergency, used = fixed["reply"], "rules", fixed["emergency"], []
    else:
        quick_reply = _quick_risk_answer(db, text, language, context)
        if quick_reply is not None:
            reply, layer, emergency, used = quick_reply, "lookup", False, ["get_district_risk"]
        else:
            layer, emergency, used = "agent", False, []
            token = current_user_id.set(user_id)  # lets tools know who is asking (own incidents only)
            loc_token = current_location.set(_location(context) if context else None)
            try:
                reply, used = _run_agent(history, text, language, context)
            except Exception:
                # Users see a safe fallback message; the real reason (wrong key, bad model name, quota) goes to the server log.
                log.exception("Thunai agent failed (provider=%s)", config.PROVIDER)
                reply, layer = FALLBACK.get(language, FALLBACK["en"]), "fallback"
            finally:
                current_user_id.reset(token)
                current_location.reset(loc_token)

    bot = ChatMessage(session_id=session_id, role="assistant", content=reply, layer=layer)
    db.add(bot)
    db.commit()
    db.refresh(bot)

    log.info("Thunai response completed layer=%s elapsed_ms=%d", layer, round((time.perf_counter() - started_at) * 1000))

    return {
        "session_id": session_id, "message_id": bot.id, "reply": reply,
        "layer": layer, "emergency": emergency,
        "quick_replies": QUICK_REPLIES.get(language, QUICK_REPLIES["en"]),
        "tools_used": used,
    }
