"""Chat tables. Uses your existing SQLAlchemy Base (adjust the import if needed)."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from app.core.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, nullable=True)
    language = Column(String(5), default="en")
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), index=True)
    role = Column(String(10))            # user | assistant
    content = Column(Text)
    layer = Column(String(10), nullable=True)   # rules | agent
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatFeedback(Base):
    __tablename__ = "chat_feedback"
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), index=True)
    helpful = Column(Boolean)
    created_at = Column(DateTime, default=datetime.utcnow)
