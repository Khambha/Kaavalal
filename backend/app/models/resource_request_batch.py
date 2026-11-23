from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class ResourceRequestBatch(Base):
    """Atomic rescuer submission and durable queue record for asynchronous triage."""

    __tablename__ = "resource_request_batches"

    id = Column(Integer, primary_key=True, index=True)
    tx_id = Column(String(60), nullable=False, unique=True, index=True)
    responder_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    help_request_id = Column(Integer, ForeignKey("help_requests.id"), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    status = Column(String(40), nullable=False, default="PENDING_AI_TRIAGE", index=True)
    triage_state = Column(String(20), nullable=False, default="PENDING", index=True)
    triage_started_at = Column(DateTime(timezone=True), nullable=True)
    ai_priority = Column(String(20), nullable=True)
    ai_summary = Column(Text, nullable=True)
    triage_context = Column(Text, nullable=True)
    triage_error = Column(Text, nullable=True)
    risk_score = Column(Float, nullable=True)
    weather_summary = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    triaged_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
