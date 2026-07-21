"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rate_limit import RequireAuthRateLimit
from app.core.security import create_access_token
from app.crud.user import authenticate_user, create_user, get_user_by_username
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services.reputation import get_user_limits

router = APIRouter()


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
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "tier_name": limits.tier_name,
            "max_teaser_length": limits.max_teaser_length,
            "max_content_length": limits.max_content_length,
            "daily_part_limit": limits.daily_part_limit,
            "min_parts_between_own": limits.min_parts_between_own,
            "can_vote": limits.can_vote,
            "parts_written_today": limits.parts_written_today,
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
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user profile with reputation tier limits."""
    return await _user_response(db, current_user)
