"""core/schemas.py — Pydantic schemas for auth, settings, and user management."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ── Auth ──────────────────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: float = 0.7
    has_api_key: bool = False
    created_at: str

    model_config = {"from_attributes": True}


# ── Settings ───────────────────────────────────────────────────────────────────
class SettingsUpdate(BaseModel):
    llm_provider: Optional[str] = Field(None, min_length=1, max_length=50)
    llm_api_key: Optional[str] = Field(None, max_length=2048)
    llm_model: Optional[str] = Field(None, min_length=1, max_length=100)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    display_name: Optional[str] = Field(None, max_length=100)
    llm_base_url: Optional[str] = Field(None, max_length=500)


class SettingsResponse(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: float
    has_api_key: bool
    display_name: Optional[str] = None
    llm_base_url: Optional[str] = None


# ── Generic ────────────────────────────────────────────────────────────────────
class MessageResponse(BaseModel):
    message: str