"""api/settings.py — /api/settings endpoints for user LLM configuration."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.models_db import User
from app.core.schemas import SettingsUpdate, SettingsResponse, MessageResponse
from app.middleware.auth import get_current_user
from app.services.providers import encrypt_api_key, decrypt_api_key, validate_provider_connection
from app.utils.logger import log

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(current_user: User = Depends(get_current_user)):
    """Return the current user's LLM settings."""
    return SettingsResponse(
        llm_provider=current_user.llm_provider,
        llm_model=current_user.llm_model,
        temperature=current_user.temperature,
        has_api_key=bool(current_user.llm_api_key_encrypted),
        display_name=current_user.display_name,
        llm_base_url=current_user.llm_base_url,
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    req: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Update the user's LLM provider, API key, model, temperature, and base URL."""
    if req.llm_provider is not None:
        current_user.llm_provider = req.llm_provider.strip().lower()

    if req.llm_api_key is not None:
        current_user.llm_api_key_encrypted = encrypt_api_key(req.llm_api_key)

    if req.llm_model is not None:
        current_user.llm_model = req.llm_model.strip()

    if req.temperature is not None:
        current_user.temperature = req.temperature

    if req.display_name is not None:
        current_user.display_name = req.display_name

    if req.llm_base_url is not None:
        current_user.llm_base_url = req.llm_base_url.strip() if req.llm_base_url.strip() else None

    await session.commit()
    await session.refresh(current_user)

    log.info("Settings updated for user %s", current_user.email)

    return SettingsResponse(
        llm_provider=current_user.llm_provider,
        llm_model=current_user.llm_model,
        temperature=current_user.temperature,
        has_api_key=bool(current_user.llm_api_key_encrypted),
        display_name=current_user.display_name,
        llm_base_url=current_user.llm_base_url,
    )


@router.post("/test", response_model=MessageResponse)
async def test_llm_connection(current_user: User = Depends(get_current_user)):
    """Test the user's configured LLM provider with a minimal API call."""
    if not current_user.llm_api_key_encrypted:
        raise HTTPException(status_code=400, detail="No API key configured. Save your API key first.")
    if not current_user.llm_provider:
        raise HTTPException(status_code=400, detail="No provider configured. Select a provider first.")
    if not current_user.llm_model:
        raise HTTPException(status_code=400, detail="No model configured. Enter a model name first.")

    api_key = decrypt_api_key(current_user.llm_api_key_encrypted)
    provider = current_user.llm_provider
    model = current_user.llm_model
    base_url = current_user.llm_base_url

    try:
        msg = await validate_provider_connection(provider, api_key, model, base_url)
        return MessageResponse(message=msg)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.warning("LLM connection test failed for %s: %s", current_user.email, e)
        error_str = str(e).lower()
        if "401" in error_str or "auth" in error_str or "unauthorized" in error_str or "invalid" in error_str:
            raise HTTPException(status_code=400, detail="Invalid API key. Please check and try again.")
        if "rate" in error_str or "429" in error_str:
            raise HTTPException(status_code=400, detail="Rate limit hit. Wait a moment and try again.")
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)[:300]}")
