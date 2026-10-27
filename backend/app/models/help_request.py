from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func

from app.core.database import Base


class HelpRequest(Base):
    __tablename__ = "help_requests"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    district = Column(String(100), nullable=False)
    lac = Column(String(150), nullable=False)
    location_description = Column(String(500), nullable=False)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    emergency_type = Column(String(100), nullable=False)

    people_affected = Column(Integer, nullable=False, default=1)

    special_assistance = Column(Text, nullable=True)

    urgency = Column(String(20), nullable=False)

    situation_description = Column(Text, nullable=False)

    image_path = Column(String(500), nullable=True)

    status = Column(
        String(30),
        nullable=False,
        default="Submitted",
        index=True,
    )

    assigned_responder_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    shelter_id = Column(Integer, ForeignKey("shelters.id"), nullable=True)

    client_request_id = Column(String(36), nullable=True, unique=True, index=True)
    eta_estimate_minutes = Column(Integer, nullable=True)

    responder_notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
