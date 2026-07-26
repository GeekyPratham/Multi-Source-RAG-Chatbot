"""api/recommend.py — /api/recommend endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from app.core.models import RecommendResponse
from app.core.models_db import User
from app.middleware.auth import get_current_user
from app.services.recommender_service import get_recommendations
from app.services.providers import decrypt_api_key
from app.utils.logger import log

router = APIRouter(prefix="/api/recommend", tags=["recommender"])


@router.post("", response_model=RecommendResponse)
async def recommend_llm(
    req: dict,
    current_user: User = Depends(get_current_user),
):
    """Analyse a task/query and return ranked LLM recommendations.
    Uses the authenticated user's stored API key.
    """
    query = req.get("query", "")
    if len(query) < 3:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters")

    if not current_user.llm_api_key_encrypted:
        raise HTTPException(
            status_code=400,
            detail="no_api_key_configured",
        )

    try:
        api_key = decrypt_api_key(current_user.llm_api_key_encrypted)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not decrypt your stored API key. Please re-enter it in Settings.",
        )

    try:
        return await get_recommendations(query, api_key)
    except Exception as e:
        error_str = str(e).lower()
        log.error("Recommend error: %s", e, exc_info=True)
        if "rate_limit_exceeded" in error_str or "rate limit exceeded" in error_str or (
            "429" in error_str and any(p in error_str for p in ["groq", "openai", "anthropic", "token"])
        ):
            raise HTTPException(status_code=429, detail="rate_limit_hit")
        if any(x in error_str for x in ["invalid api key", "invalid_api_key", "incorrect api key", "authentication failed", "unauthorized"]) and "401" in error_str:
            raise HTTPException(status_code=401, detail="invalid_api_key")
        raise HTTPException(status_code=500, detail=str(e))