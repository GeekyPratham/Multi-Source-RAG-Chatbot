"""middleware/auth.py — JWT dependency and current user extraction."""
from __future__ import annotations
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.models_db import User
from app.services.auth_service import decode_access_token, get_user_by_id

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT access token.

    Raises 401 if the token is missing, invalid, or the user doesn't exist.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user_id_str = decode_access_token(token)
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await get_user_by_id(user_uuid, session)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None if no valid token is provided."""
    if credentials is None:
        return None
    user_id_str = decode_access_token(credentials.credentials)
    if user_id_str is None:
        return None
    try:
        return await get_user_by_id(uuid.UUID(user_id_str), session)
    except (ValueError, Exception):
        return None