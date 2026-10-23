from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    # Older local databases created this column as actor_id. Keep the Python
    # attribute admin_user_id for the API while mapping to that persisted name.
    admin_user_id = Column("actor_id", Integer, ForeignKey("admin_users.id"), nullable=False, index=True)
    action = Column(String(80), nullable=False, index=True)
    target_type = Column(String(50), nullable=True)
    target_id = Column(Integer, nullable=True, index=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
