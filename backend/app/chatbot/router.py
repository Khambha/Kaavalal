from fastapi import APIRouter, Depends, Request, HTTPException
from pathlib import Path
import sqlite3
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.rate_limit import limiter
from . import config
from .models import ChatMessage, ChatFeedback
from .schemas import ChatRequest, ChatResponse, FeedbackRequest
from .service import handle_message
from .auth_hook import get_optional_user_id

router = APIRouter(prefix="/chat", tags=["chatbot"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/status")
def chatbot_status(db: Session = Depends(get_db)):
    """Safe diagnostics for the client; reports configuration presence, never credentials."""
    key_by_provider = {
        "gemini": config.GOOGLE_API_KEY,
        "groq": config.GROQ_API_KEY,
        "openrouter": config.OPENROUTER_API_KEY,
        "anthropic": config.ANTHROPIC_API_KEY,
    }
    provider_configured = (
        bool(config.OLLAMA_BASE_URL) if config.PROVIDER == "ollama"
        else bool(key_by_provider.get(config.PROVIDER))
    )
    provider_supported = config.PROVIDER in config.DEFAULT_MODELS
    try:
        db.execute(text("SELECT 1"))
        database = "available"
    except Exception:
        db.rollback()
        database = "unavailable"
    reference_models = {}
    try:
        from .ref_models import RefCamp, RefHospital, RefTalukEOC, RefWaterKiosk
        for label, model in (("camps", RefCamp), ("hospitals", RefHospital),
                             ("taluk_contacts", RefTalukEOC), ("water_kiosks", RefWaterKiosk)):
            try:
                reference_models[label] = db.query(model).count()
            except Exception:
                db.rollback()
                reference_models[label] = None
    except Exception:
        reference_models = {"camps": None, "hospitals": None, "taluk_contacts": None, "water_kiosks": None}
    vector_db = Path(config.VECTOR_DIR) / "chroma.sqlite3"
    knowledge_index = "missing"
    if vector_db.is_file():
        try:
            # uri=True matters here: without it Windows SQLite treats "file:///..."
            # as a literal filename and reports the existing Chroma index as unavailable.
            conn = sqlite3.connect(
                f"{vector_db.resolve().as_uri()}?mode=ro", uri=True, timeout=1
            )
            try:
                collection = conn.execute(
                    "SELECT id FROM collections WHERE name = ?", ("kaavalal_kb",)
                ).fetchone()
                if collection:
                    count = conn.execute(
                        "SELECT COUNT(*) FROM embeddings e "
                        "JOIN segments s ON s.id = e.segment_id WHERE s.collection = ?",
                        (collection[0],),
                    ).fetchone()[0]
                    knowledge_index = "ready" if count > 0 else "empty"
                else:
                    knowledge_index = "collection_missing"
            finally:
                conn.close()
        except (sqlite3.Error, ValueError):
            knowledge_index = "unavailable"
    return {
        "database": database,
        "provider": config.PROVIDER,
        "model": config.CHATBOT_MODEL or config.DEFAULT_MODELS.get(config.PROVIDER),
        "provider_supported": provider_supported,
        "provider_credential_configured": provider_configured,
        "knowledge_index": knowledge_index,
        "ksdma_reference_data_enabled": config.KSDMA_DATA_READY,
        "ksdma_reference_rows": reference_models,
        "provider_credential_note": "Presence only; the provider key/model has not been verified by a live request.",
    }


@router.post("", response_model=ChatResponse)
@limiter.limit(config.RATE_LIMIT)
def chat(request: Request, body: ChatRequest, db: Session = Depends(get_db),
         user_id=Depends(get_optional_user_id)):
    ctx = body.context.model_dump() if body.context else None
    return handle_message(db, body.session_id, body.message.strip(), body.language, ctx, user_id)


@router.post("/feedback")
def feedback(body: FeedbackRequest, db: Session = Depends(get_db)):
    if not db.get(ChatMessage, body.message_id):
        raise HTTPException(404, "Message not found")
    db.add(ChatFeedback(message_id=body.message_id, helpful=body.helpful))
    db.commit()
    return {"ok": True}
