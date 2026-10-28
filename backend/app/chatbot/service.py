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
    "en": "Sorry, I'm having trouble right now. For emergencies call 112; for flood help call 1077.",
    "ml": "ക്ഷമിക്കണം, ഇപ്പോൾ ഒരു തടസ്സമുണ്ട്. അടിയന്തര സാഹചര്യത്തിൽ 112 / 1077 ൽ വിളിക്കുക.",
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
    """Answer short risk lookups from Kaavalal's DB without the multi-call LLM agent."""
    if len(text.split()) > 12 or not _RISK_QUESTION_RE.search(text):
        return None

    hazards = (
        (r"\b(flood|flooding)\b|വെള്ളപ്പൊക്കം", "flood_risk", "flood"),
        (r"\b(landslide|landslip)\b|ഉരുൾപൊട്ടൽ|മണ്ണിടിച്ചിൽ", "landslide_risk", "landslide"),
        (r"\b(drought)\b|വരൾച്ച", "drought_risk", "drought"),
    )
    selected = next(((field, label) for pattern, field, label in hazards if re.search(pattern, text, re.IGNORECASE)), None)
    field, label = selected if selected else ("overall_risk", "overall")
    district = config.normalize_district(text)
    if not district and context:
        district = config.normalize_district(context.get("district"))

    if not district:
        return "ഏത് ജില്ലയുടെ അപകടസാധ്യതയാണ് അറിയേണ്ടത്?" if language == "ml" else "Which Kerala district should I check?"

    from app.models.location import Location
    from app.models.risk import RiskData

    try:
        record = (
            db.query(RiskData)
            .join(Location, Location.id == RiskData.location_id)
            .filter(Location.name == district, Location.location_type == "DISTRICT")
            .order_by(RiskData.recorded_at.desc())
            .first()
        )
    except Exception:
        log.exception("Thunai quick risk lookup failed for district=%s", district)
        return (
            f"ഇപ്പോൾ {district} ജില്ലയുടെ അപകടസാധ്യതാ വിവരങ്ങൾ ലഭ്യമല്ല. ഔദ്യോഗിക മുന്നറിയിപ്പുകൾ KSDMA/IMD-യിൽ പരിശോധിക്കുക."
            if language == "ml" else
            f"Risk data for {district} is unavailable right now. Check official KSDMA/IMD alerts for current warnings."
        )
    if record is None or getattr(record, field) is None:
        return (
            f"{district} ജില്ലയ്ക്ക് നിലവിൽ സംഭരിച്ച അപകടസാധ്യതാ വിലയിരുത്തൽ ലഭ്യമല്ല. ഔദ്യോഗിക മുന്നറിയിപ്പുകൾ KSDMA/IMD-യിൽ പരിശോധിക്കുക."
            if language == "ml" else
            f"I don't have a stored risk assessment for {district}. Check official KSDMA/IMD alerts for current warnings."
        )

    score = float(getattr(record, field))
    band = "Low" if score < 40 else "Moderate" if score < 60 else "High" if score < 75 else "Severe"
    recorded = record.recorded_at.strftime("%Y-%m-%d %H:%M") if record.recorded_at else "time unavailable"
    if language == "ml":
        return (f"{district} ജില്ലയിലെ ഏറ്റവും പുതിയ {label} അപകടസാധ്യതാ കണക്ക് {score:g}/100 ({band}) ആണ്; രേഖപ്പെടുത്തിയത് {recorded}. "
                "ഇത് കാവലാളിന്റെ സൂചനാപരമായ വിലയിരുത്തലാണ്, തത്സമയ ഔദ്യോഗിക പ്രവചനമല്ല. ഔദ്യോഗിക മുന്നറിയിപ്പുകൾ KSDMA/IMD-യിൽ പരിശോധിക്കുക.")
    return (f"Kaavalal's latest {label} risk estimate for {district} is {score:g}/100 ({band}), recorded {recorded}. "
            "This is an illustrative Kaavalal estimate, not a live official forecast. Check KSDMA/IMD for current warnings.")


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
    # A session belongs to whoever created it: never continue someone else's conversation.
    if existing is not None and existing.user_id is not None and existing.user_id != user_id:
        existing, session_id = None, None
    if existing is None:
        session_id = session_id or str(uuid.uuid4())
        if db.get(ChatSession, session_id) is not None:  # id taken by another session
            session_id = str(uuid.uuid4())
        db.add(ChatSession(id=session_id, user_id=user_id, language=language))
        db.commit()
    elif existing.user_id is None and user_id is not None:
        existing.user_id = user_id
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
