from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class Shelter(Base):
    __tablename__ = "shelters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    building_type = Column(String(80), nullable=False)
    district = Column(String(100), nullable=False, index=True)
    lac = Column(String(150), nullable=False, index=True)
    address = Column(String(500), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    capacity = Column(Integer, nullable=False)
    occupied = Column(Integer, nullable=False, default=0)
    is_active = Column(Integer, nullable=False, default=1)
    source_key = Column(String(120), nullable=True, unique=True)
    source_name = Column(String(100), nullable=True)
    source_row = Column(Integer, nullable=True)
    needs_review = Column(Boolean, nullable=False, default=False)
    lac_assignment_method = Column(String(40), nullable=True)
    lac_distance_km = Column(Float, nullable=True)
    created_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ShelterCandidate(Base):
    __tablename__ = "shelter_candidates"

    id = Column(Integer, primary_key=True, index=True)
    source_key = Column(String(140), nullable=False, unique=True)
    source_name = Column(String(100), nullable=False)
    source_sheet = Column(String(40), nullable=False)
    source_row = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    district = Column(String(100), nullable=False, index=True)
    lsg = Column(String(150), nullable=False)
    address = Column(String(500), nullable=False)
    suggested_latitude = Column(Float, nullable=True)
    suggested_longitude = Column(Float, nullable=True)
    geocode_confidence = Column(String(20), nullable=False)
    geocode_match_type = Column(String(50), nullable=False)
    geocode_result_name = Column(String(200), nullable=True)
    geocode_result_address = Column(String(500), nullable=True)
    geocode_result_url = Column(String(500), nullable=True)
    geocode_note = Column(Text, nullable=False)
    review_status = Column(String(30), nullable=False, default="Pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ShelterRequest(Base):
    __tablename__ = "shelter_requests"

    id = Column(Integer, primary_key=True, index=True)
    citizen_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    preferred_shelter_id = Column(Integer, ForeignKey("shelters.id"), nullable=False)
    assigned_shelter_id = Column(Integer, ForeignKey("shelters.id"), nullable=True)
    district = Column(String(100), nullable=False, index=True)
    lac = Column(String(150), nullable=False, index=True)
    household_name = Column(String(150), nullable=False)
    aadhaar_last4 = Column(String(4), nullable=False)
    phone = Column(String(20), nullable=False)
    people_count = Column(Integer, nullable=False)
    citizen_location = Column(String(500), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    id_photo_path = Column(String(255), nullable=True)
    special_needs = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="Pending", index=True)
    responder_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    client_request_id = Column(String(36), nullable=True, unique=True, index=True)
    eta_estimate_minutes = Column(Integer, nullable=True)


class RequestStatusEvent(Base):
    __tablename__ = "request_status_events"

    id = Column(Integer, primary_key=True, index=True)
    help_request_id = Column(Integer, ForeignKey("help_requests.id"), nullable=True, index=True)
    shelter_request_id = Column(Integer, ForeignKey("shelter_requests.id"), nullable=True, index=True)
    status = Column(String(30), nullable=False)
    note = Column(Text, nullable=True)
    actor_role = Column(String(30), nullable=False, default="system")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
