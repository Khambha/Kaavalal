from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(180), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)
    district = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    reviewed_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
