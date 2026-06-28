"""core/models.py — all Pydantic schemas used by the API."""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Auth / API Key ────────────────────────────────────────────────────────────
class ApiKeyValidateRequest(BaseModel):
    api_key: str


class ApiKeyValidateResponse(BaseModel):
    valid: bool
    message: str


# ── LLM Recommender ───────────────────────────────────────────────────────────
class RecommendRequest(BaseModel):
    query: str = Field(..., min_length=3, description="The task or query to analyse")
    api_key: str = Field(..., description="User's Groq API key")


class LLMRecommendation(BaseModel):
    name: str
    provider: str
    tier: str                   # "free" | "paid"
    best_for: str
    context_window: str
    speed: str                  # "fast" | "medium" | "slow"
    cost: str
    why_recommended: str
    groq_model_id: Optional[str] = None   # if available on Groq free tier


class RecommendResponse(BaseModel):
    query_analysis: str
    task_type: str
    recommendations: list[LLMRecommendation]
    top_pick: str
    reasoning: str


# ── RAG / Chat ────────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str          # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    api_key: str = ""
    model_name: str = "llama-3.3-70b-versatile"
    memory_turns: int = 6
    history: list[ChatMessage] = []
    session_id: str = "default"
    temperature: float = 0.7
    provider: str = "groq"
    base_url: str | None = None


class ToolStep(BaseModel):
    step: int
    tool: str
    tool_input: Any
    observation: str


class ChatResponse(BaseModel):
    answer: str
    tool_steps: list[ToolStep] = []
    tools_used: list[str] = []
    answered_from_history: bool = False


# ── Sources ───────────────────────────────────────────────────────────────────
class AddUrlRequest(BaseModel):
    url: str
    session_id: str = "default"


class SourceResponse(BaseModel):
    success: bool
    message: str
    tool_name: Optional[str] = None
    title: Optional[str] = None


class UploadPdfResponse(BaseModel):
    success: bool
    message: str
    tool_name: Optional[str] = None
    filename: Optional[str] = None
