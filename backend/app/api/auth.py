"""api/auth.py — /api/auth endpoints: signup, login, refresh, logout, validate."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.models_db import User
from app.core.schemas import (
    SignupRequest, LoginRequest, TokenResponse, UserResponse,
    RefreshRequest, RefreshResponse, MessageResponse,
)
from app.middleware.auth import get_current_user
from app.services import session_store, user_store
from app.services.auth_service import (
    hash_password, verify_password, create_access_token,
    issue_refresh_token, rotate_refresh_token,
    delete_refresh_token_redis, get_user_by_email,
)
from app.utils.logger import log

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_to_response(user: User) -> UserResponse:
    # Normalize provider: could be an Enum member, a string, or None
    provider = None
    if getattr(user, 'llm_provider', None) is not None:
        try:
            # If it's an Enum instance
            provider = user.llm_provider.value if hasattr(user.llm_provider, 'value') else user.llm_provider
        except Exception:
            provider = user.llm_provider

    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        llm_provider=provider,
        llm_model=user.llm_model,
        temperature=user.temperature,
        has_api_key=bool(user.llm_api_key_encrypted),
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


# ── Signup ─────────────────────────────────────────────────────────────────────
@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(req: SignupRequest, session: AsyncSession = Depends(get_db)):
    """Create a new user account and return JWT tokens."""
    existing = await get_user_by_email(req.email, session)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Create user without default provider/model — user must configure these in Settings
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
        temperature=0.7,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    access_token = create_access_token(str(user.id))
    refresh_token = await issue_refresh_token(user.id)

    log.info("New user signed up: %s (id=%s)", user.email, user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_to_response(user),
    )


# ── Login ──────────────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, session: AsyncSession = Depends(get_db)):
    """Authenticate with email + password and receive JWT tokens."""
    user = await get_user_by_email(req.email, session)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(str(user.id))
    refresh_token = await issue_refresh_token(user.id)

    log.info("User logged in: %s", user.email)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_to_response(user),
    )


# ── Refresh ────────────────────────────────────────────────────────────────────
@router.post("/refresh/v2", response_model=RefreshResponse)
async def refresh_v2(req: dict):
    """Exchange refresh token for new tokens. Send {"refresh_token": "...", "user_id": "..."}."""
    raw_token = req.get("refresh_token", "")
    user_id = req.get("user_id", "")
    if not raw_token or not user_id:
        raise HTTPException(status_code=400, detail="refresh_token and user_id are required")

    result = await rotate_refresh_token(user_id, raw_token)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    new_access, new_refresh, _ = result
    return RefreshResponse(access_token=new_access, refresh_token=new_refresh)


# ── Logout ─────────────────────────────────────────────────────────────────────
@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Invalidate the current user's refresh token and purge their vectors.

    On logout we delete every user-owned Chroma collection, the user's
    document/chunk rows, and their in-memory retrieval tools ("purge on
    logout"), so no vector data survives a session.
    """
    user_key = str(current_user.id)
    await delete_refresh_token_redis(user_key)

    try:
        removed = await user_store.purge_user_data(
            user_id=current_user.id, session=session, reason="logout"
        )
        session_store.clear_session(user_key)
        log.info(
            "User logged out: %s — purged %d vector collection(s) + document rows",
            current_user.email, removed,
        )
    except Exception as e:  # pragma: no cover - never block logout on cleanup
        log.error("Logout purge failed for user %s: %s", current_user.email, e)

    return MessageResponse(message="Logged out successfully")


# ── Get current user profile ──────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return _user_to_response(current_user)


# ── Legacy API key validate (kept for backward compat) ─────────────────────────
@router.post("/validate")
async def validate_key(req: dict):
    """Legacy endpoint — kept for backwards compatibility with existing clients."""
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage

    api_key = req.get("api_key", "")
    if not api_key:
        return {"valid": False, "message": "Missing API key"}

    try:
        llm = ChatGroq(groq_api_key=api_key, model_name="llama3-8b-8192", max_tokens=5)
        await llm.ainvoke([HumanMessage(content="hi")])
        return {"valid": True, "message": "API key is valid ✓"}
    except Exception as e:
        msg = str(e)
        if "401" in msg or "auth" in msg.lower() or "invalid" in msg.lower():
            return {"valid": False, "message": "Invalid API key. Please check and try again."}
        return {"valid": False, "message": f"Could not validate: {msg[:100]}"}