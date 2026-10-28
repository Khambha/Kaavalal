from typing import Optional, List
from pydantic import BaseModel, Field
from .config import MAX_MESSAGE_CHARS


class ChatContext(BaseModel):
    """What the Kaavalal dashboard is currently showing the user."""
    district: Optional[str] = Field(default=None, max_length=50)
    page: Optional[str] = Field(default=None, max_length=50)
    # Only sent after the user presses 'Use my location'. Used for nearest-camp / water-kiosk lookups, never stored.
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    language: str = Field(default="en", pattern="^(en|ml)$")
    context: Optional[ChatContext] = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: int
    reply: str
    layer: str
    emergency: bool = False
    quick_replies: List[str] = []
    tools_used: List[str] = []


class FeedbackRequest(BaseModel):
    message_id: int
    helpful: bool
