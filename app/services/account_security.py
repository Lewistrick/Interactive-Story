"""Forced password reset and JWT session invalidation helpers."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User


async def force_password_reset(db: AsyncSession, user: User) -> None:
    """Require a password change and invalidate outstanding JWTs.

    Bumps ``token_version`` so existing access tokens fail validation, and sets
    ``must_reset_password`` so the user can only use password-change endpoints
    until they set a new password.

    Args:
        db: Database session.
        user: Account to lock into reset mode.
    """
    user.must_reset_password = True
    user.token_version = int(user.token_version or 0) + 1
    await db.commit()
    await db.refresh(user)


async def complete_password_change(
    db: AsyncSession,
    user: User,
    *,
    new_password: str,
) -> None:
    """Apply a new password hash, clear the reset flag, and rotate token version.

    Args:
        db: Database session.
        user: Authenticated user changing their password.
        new_password: Plain-text password to store (hashed).
    """
    user.password_hash = get_password_hash(new_password)
    user.must_reset_password = False
    user.token_version = int(user.token_version or 0) + 1
    await db.commit()
    await db.refresh(user)
