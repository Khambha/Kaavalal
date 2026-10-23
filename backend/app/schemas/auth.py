from typing import Literal

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    role: Literal["citizen", "rescuer"] = "citizen"

    district: str = Field(min_length=2, max_length=100)
    nearest_lac: str = Field(min_length=2, max_length=100)

    # Optional for citizens; required by backend logic for rescuers
    organization_code: str | None = None
    rescuer_id: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    district: str | None = None
    nearest_lac: str | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
