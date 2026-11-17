from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class ResourceAssetAssignment(Base):
    __tablename__ = "resource_asset_assignments"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("resource_requests.id"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("resource_assets.id"), nullable=False, index=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    returned_at = Column(DateTime(timezone=True), nullable=True)
    return_condition = Column(String(30), nullable=True)
    return_note = Column(Text, nullable=True)
