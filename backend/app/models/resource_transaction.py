from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class ResourceTransaction(Base):
    __tablename__ = "resource_transactions"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resource_items.id"), nullable=False, index=True)
    responder_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    help_request_id = Column(Integer, ForeignKey("help_requests.id"), nullable=True, index=True)
    resource_name = Column(String(120), nullable=False)
    district = Column(String(100), nullable=False, index=True)
    unit = Column(String(40), nullable=False)
    quantity = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
