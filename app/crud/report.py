"""CRUD helpers for story-part reports."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report


async def get_user_report(
    db: AsyncSession,
    story_part_id: str,
    reporter_id: str,
) -> Optional[Report]:
    """Return an existing report by this user for the part, if any."""
    result = await db.execute(
        select(Report).where(
            Report.story_part_id == story_part_id,
            Report.reporter_id == reporter_id,
        )
    )
    return result.scalar_one_or_none()


async def create_report(
    db: AsyncSession,
    *,
    story_part_id: str,
    reporter_id: str,
    reason: Optional[str] = None,
) -> Report:
    """Create a new report row."""
    report = Report(
        story_part_id=story_part_id,
        reporter_id=reporter_id,
        reason=reason,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def count_reports_for_part(db: AsyncSession, story_part_id: str) -> int:
    """Count distinct reporters for a story part."""
    result = await db.execute(
        select(func.count()).select_from(Report).where(Report.story_part_id == story_part_id)
    )
    return int(result.scalar_one())
