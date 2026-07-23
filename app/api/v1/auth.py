"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_allowing_password_reset
from app.core.rate_limit import RequireAuthRateLimit
from app.core.security import create_access_token, verify_password
from app.crud.user import authenticate_user, create_user, get_user_by_username
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import PasswordChange, Token, UserCreate, UserLogin, UserResponse
from app.services.account_security import complete_password_change
from app.services.reputation import get_user_limits

router = APIRouter()


def _access_token_for(user: User) -> str:
    """Issue a JWT that embeds the user's current token_version."""
    return create_access_token(data={"sub": user.username, "tv": int(user.token_version or 0)})


async def _user_response(db: AsyncSession, user: User) -> UserResponse:
    """Build a UserResponse including reputation tier limits."""
    limits = await get_user_limits(db, user)
    return UserResponse.model_validate(
        {
            "id": user.id,
            "username": user.username,
            "reputation_score": user.reputation_score,
            "is_quarantined": user.is_quarantined,
            "quarantine_reason": user.quarantine_reason,
            "quarantine_until": user.quarantine_until,
            "is_moderator": user.is_moderator,
            "is_blocked": user.is_blocked,
            "must_reset_password": bool(user.must_reset_password),
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "tier_name": limits.tier_name,
            "max_teaser_length": limits.max_teaser_length,
            "max_content_length": limits.max_content_length,
            "daily_part_limit": limits.daily_part_limit,
            "min_parts_between_own": limits.min_parts_between_own,
            "can_vote": limits.can_vote,
            "parts_written_today": limits.parts_written_today,
            "can_create_root": limits.can_create_root,
            "min_reputation_create_root": limits.min_reputation_create_root,
            "open_root_trees": limits.open_root_trees,
            "max_concurrent_open_trees": limits.max_concurrent_open_trees,
        }
    )


@router.post(
    "/register",
    response_model=UserResponse,
    dependencies=[RequireAuthRateLimit],
)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    existing_user = await get_user_by_username(db, username=user.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered"
        )
    db_user = await create_user(db, user)
    return await _user_response(db, db_user)


@router.post(
    "/login",
    response_model=Token,
    dependencies=[RequireAuthRateLimit],
)
async def login(user_credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and return a JWT access token."""
    user = await authenticate_user(db, user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.is_blocked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is blocked")
    access_token = _access_token_for(user)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "must_reset_password": bool(user.must_reset_password),
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user_allowing_password_reset),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user profile with reputation tier limits."""
    return await _user_response(db, current_user)


@router.post("/change-password", response_model=Token, dependencies=[RequireAuthRateLimit])
async def change_password(
    body: PasswordChange,
    current_user: User = Depends(get_current_user_allowing_password_reset),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password and issue a fresh access token.

    Allowed while ``must_reset_password`` is set so compromised accounts can
    recover after velocity + IP/fingerprint trips.
    """
    if len(body.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters",
        )
    if not verify_password(body.current_password, str(current_user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from the current password",
        )
    await complete_password_change(db, current_user, new_password=body.new_password)
    return {
        "access_token": _access_token_for(current_user),
        "token_type": "bearer",
        "must_reset_password": False,
    }
