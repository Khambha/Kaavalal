from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class ResourceRequest(Base):
    __tablename__ = "resource_requests"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resource_items.id"), nullable=False, index=True)
    responder_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reviewer_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    help_request_id = Column(Integer, ForeignKey("help_requests.id"), nullable=True, index=True)
    district = Column(String(100), nullable=False, index=True)
    resource_name = Column(String(120), nullable=False)
    unit = Column(String(40), nullable=False)
    inventory_mode = Column(String(20), nullable=False, default="Bulk")
    quantity_requested = Column(Integer, nullable=False)
    quantity_granted = Column(Integer, nullable=True)
    quantity_returned = Column(Integer, nullable=False, default=0)
    quantity_quarantined = Column(Integer, nullable=False, default=0)
    is_returnable = Column(Boolean, nullable=False, default=False)
    priority = Column(String(20), nullable=False, default="Standard")
    rejection_reason = Column(Text, nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="Pending", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
