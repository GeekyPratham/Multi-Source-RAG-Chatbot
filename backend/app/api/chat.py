"""api/chat.py — /api/chat endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from app.core.models import ChatRequest, ChatResponse
from app.core.models_db import User
from app.services.agent_service import run_agent
from app.services.providers import decrypt_api_key
from app.middleware.auth import get_optional_user
from app.utils.logger import log

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    current_user: User | None = Depends(get_optional_user),
):
    """Run the RAG agent with the user's message and return the answer.

    Supports two modes:
    1. Legacy: client provides api_key, model_name directly
    2. Authenticated: user is logged in, backend uses their stored provider config
       (overrides temperature from user settings, uses stored API key)
    """
    try:
        # If user is authenticated and no explicit api_key is given,
        # use their stored provider configuration
        if current_user and not req.api_key:
            # Check if user has configured settings
            if not current_user.llm_provider:
                raise HTTPException(
                    status_code=400,
                    detail="settings_not_configured",
                )
            if not current_user.llm_model:
                raise HTTPException(
                    status_code=400,
                    detail="settings_not_configured",
                )
            if not current_user.llm_api_key_encrypted:
                raise HTTPException(
                    status_code=400,
                    detail="no_api_key_configured",
                )

            try:
                req.api_key = decrypt_api_key(current_user.llm_api_key_encrypted)
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="stored_key_corrupted",
                )

            req.provider = current_user.llm_provider or "groq"
            req.model_name = current_user.llm_model or req.model_name
            req.base_url = current_user.llm_base_url
            # Temperature from user settings overrides request, unless request explicitly set it
            if req.temperature == 0.7:  # default value, user might have changed it
                req.temperature = current_user.temperature

        if not req.api_key:
            raise HTTPException(
                status_code=400,
                detail="no_api_key_configured",
            )

        current_user_id = str(current_user.id) if current_user else None
        return await run_agent(req, user_id=current_user_id)
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e).lower()
        log.error("Chat error: %s", e, exc_info=True)
        # Only flag rate limit when it's clearly from the LLM provider (not tool calls)
        if "rate_limit_exceeded" in error_str or "rate limit exceeded" in error_str or (
            "429" in error_str and any(p in error_str for p in ["groq", "openai", "anthropic", "llm", "token"])
        ):
            raise HTTPException(status_code=429, detail="rate_limit_hit")
        # Only flag invalid API key on explicit auth failures from the LLM provider
        if any(x in error_str for x in ["invalid api key", "invalid_api_key", "incorrect api key", "authentication failed", "unauthorized"])  and "401" in error_str:
            raise HTTPException(status_code=401, detail="invalid_api_key")
        raise HTTPException(status_code=500, detail=str(e))
