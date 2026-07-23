"""Authentication dependencies and current-user resolution."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.crud.user import get_user_by_username
from app.db.session import get_db
from app.models.user import User
from app.services.quarantine import maybe_expire_user_quarantine

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


async def _user_from_credentials(
    credentials: HTTPAuthorizationCredentials,
    db: AsyncSession,
    *,
    allow_password_reset_pending: bool,
) -> User:
    """Resolve and validate the JWT bearer user."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username = payload.get("sub")
    if not isinstance(username, str) or not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await get_user_by_username(db, username=username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_version = payload.get("tv", 0)
    try:
        claim_version = int(token_version)
    except (TypeError, ValueError):
        claim_version = -1
    if claim_version != int(user.token_version or 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is blocked",
        )
    if user.must_reset_password and not allow_password_reset_pending:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="password_reset_required",
        )
    await maybe_expire_user_quarantine(db, user)
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require a valid authenticated user who is not pending a forced password reset."""
    return await _user_from_credentials(credentials, db, allow_password_reset_pending=False)


async def get_current_user_allowing_password_reset(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require auth even when ``must_reset_password`` is set (for /me and change-password)."""
    return await _user_from_credentials(credentials, db, allow_password_reset_pending=True)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Return the current user when a valid token is present, otherwise None."""
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return None
    username = payload.get("sub")
    if not isinstance(username, str) or not username:
        return None
    user = await get_user_by_username(db, username=username)
    if user is None or user.is_blocked:
        return None
    token_version = payload.get("tv", 0)
    try:
        claim_version = int(token_version)
    except (TypeError, ValueError):
        return None
    if claim_version != int(user.token_version or 0):
        return None
    if user.must_reset_password:
        return None
    await maybe_expire_user_quarantine(db, user)
    return user


async def get_current_moderator(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require an authenticated moderator account."""
    if not current_user.is_moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator access required",
        )
    return current_user
