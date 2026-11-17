from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.core.database import Base


class ResourceAsset(Base):
    __tablename__ = "resource_assets"
    __table_args__ = (UniqueConstraint("asset_identifier", name="uq_resource_asset_identifier"),)

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resource_items.id"), nullable=False, index=True)
    asset_identifier = Column(String(120), nullable=False)
    status = Column(String(30), nullable=False, default="Available", index=True)
    assigned_request_id = Column(Integer, ForeignKey("resource_requests.id"), nullable=True, index=True)
    maintenance_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
