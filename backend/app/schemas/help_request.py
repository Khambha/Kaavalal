from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class HelpRequestCreate(BaseModel):
    district: str = Field(..., min_length=1, max_length=100)
    lac: str = Field(..., min_length=1, max_length=150)

    location_description: str = Field(
        ..., min_length=1, max_length=500
    )

    emergency_type: str = Field(
        ..., min_length=1, max_length=100
    )

    people_affected: int = Field(..., ge=1)

    special_assistance: Optional[str] = None

    urgency: str = Field(
        ..., min_length=1, max_length=20
    )

    situation_description: str = Field(
        ..., min_length=1, max_length=5000
    )

    latitude: Optional[float] = None
    longitude: Optional[float] = None


class HelpRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int

    district: str
    lac: str
    location_description: str

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    emergency_type: str
    people_affected: int

    special_assistance: Optional[str] = None
    urgency: str
    situation_description: str

    image_path: Optional[str] = None
    status: str

    assigned_responder_id: Optional[int] = None
    responder_notes: Optional[str] = None

    created_at: datetime
    updated_at: datetime