from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HelpRequestMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class HelpRequestMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    help_request_id: int
    sender_user_id: int
    sender_role: str
    sender_name: str
    message: str
    created_at: datetime
