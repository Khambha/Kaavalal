from fastapi import APIRouter, Depends, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from . import config
from .models import ChatMessage, ChatFeedback
from .schemas import ChatRequest, ChatResponse, FeedbackRequest
from .service import handle_message
from .auth_hook import get_optional_user_id

router = APIRouter(prefix="/chat", tags=["chatbot"])
limiter = Limiter(key_func=get_remote_address)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
