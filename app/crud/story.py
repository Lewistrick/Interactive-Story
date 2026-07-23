"""CRUD operations for story parts and votes."""

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.story_part import StoryPart, VoteType
from app.models.vote import Vote
from app.schemas.story import StoryPartCreate, StoryPartTree


async def get_story_part_by_id(db: AsyncSession, story_id: str) -> StoryPart | None:
    """Fetch a story part by ID with author loaded."""
    result = await db.execute(
        select(StoryPart).options(selectinload(StoryPart.author)).where(StoryPart.id == story_id)
    )
    return result.scalar_one_or_none()


async def get_root_stories(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    include_quarantined: bool = False,
) -> list[StoryPart]:
    """List root stories ordered by newest first."""
    query = (
        select(StoryPart)
        .options(selectinload(StoryPart.author))
        .where(StoryPart.parent_part_id.is_(None))
    )

    if not include_quarantined:
        query = query.where(StoryPart.is_quarantined == False)  # noqa: E712

    query = query.order_by(StoryPart.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_story_children(
    db: AsyncSession,
    parent_id: str,
    include_quarantined: bool = False,
) -> list[StoryPart]:
    """List direct children ordered by vote_score (desc), then newest."""
    query = (
        select(StoryPart)
        .options(selectinload(StoryPart.author))
        .where(StoryPart.parent_part_id == parent_id)
    )

    if not include_quarantined:
        query = query.where(StoryPart.is_quarantined == False)  # noqa: E712

    query = query.order_by(
        StoryPart.vote_score.desc(),
        StoryPart.created_at.desc(),
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def create_story_part(
    db: AsyncSession,
    story: StoryPartCreate,
    author_id: str,
) -> StoryPart:
    """Create a root story or continuation and set depth_level."""
    depth_level = 0
    if story.parent_part_id:
        parent = await get_story_part_by_id(db, str(story.parent_part_id))
        if parent:
            depth_level = parent.depth_level + 1

    db_story = StoryPart(
        **story.model_dump(),
        author_id=author_id,
        depth_level=depth_level,
    )
    db.add(db_story)
    await db.commit()
    await db.refresh(db_story)
    return db_story


async def get_children_count(db: AsyncSession, story_id: str) -> int:
    """Count direct children of a story part."""
    result = await db.execute(
        select(func.count(StoryPart.id)).where(StoryPart.parent_part_id == story_id)
    )
    return result.scalar() or 0


async def delete_story_part(db: AsyncSession, story: StoryPart) -> UUID | None:
    """Hard-delete a story part and its votes/reports.

    Returns:
        Parent part id if any (for score refresh), else ``None``.
    """
    from app.crud.report import delete_reports_for_part

    parent_id = story.parent_part_id
    await delete_reports_for_part(db, str(story.id))
    await db.delete(story)
    await db.commit()
    return parent_id


async def get_latest_child_by_author(
    db: AsyncSession,
    parent_id: str | UUID,
    author_id: str | UUID,
) -> StoryPart | None:
    """Most recent direct child by ``author_id`` under ``parent_id``, if any."""
    result = await db.execute(
        select(StoryPart)
        .where(
            and_(
                StoryPart.parent_part_id == parent_id,
                StoryPart.author_id == author_id,
            )
        )
        .order_by(StoryPart.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_open_root_stories_by_author(
    db: AsyncSession,
    author_id: str | UUID,
) -> int:
    """Count non-quarantined root stories authored by the user."""
    result = await db.execute(
        select(func.count(StoryPart.id)).where(
            and_(
                StoryPart.parent_part_id.is_(None),
                StoryPart.author_id == author_id,
                StoryPart.is_quarantined == False,  # noqa: E712
            )
        )
    )
    return int(result.scalar() or 0)


async def get_user_vote(
    db: AsyncSession,
    story_id: str,
    user_id: str,
) -> Vote | None:
    """Get a user's vote on a story part, if any."""
    result = await db.execute(
        select(Vote).where(and_(Vote.story_part_id == story_id, Vote.user_id == user_id))
    )
    return result.scalar_one_or_none()


async def create_vote(
    db: AsyncSession,
    story_id: str,
    user_id: str,
    vote_type: str,
) -> Vote:
    """Create a new vote and update the story's vote_score."""
    db_vote = Vote(
        story_part_id=story_id,
        user_id=user_id,
        vote_type=VoteType(vote_type),
    )
    db.add(db_vote)

    story = await get_story_part_by_id(db, story_id)
    if story:
        if vote_type == VoteType.UP or vote_type == VoteType.UP.value:
            story.vote_score += 1
        else:
            story.vote_score -= 1

    await db.commit()
    await db.refresh(db_vote)
    return db_vote


async def update_vote(
    db: AsyncSession,
    existing_vote: Vote,
    new_vote_type: str,
) -> Vote:
    """Change an existing vote type and adjust the story's vote_score."""
    old_type = existing_vote.vote_type
    existing_vote.vote_type = VoteType(new_vote_type)

    story = await get_story_part_by_id(db, str(existing_vote.story_part_id))
    if story:
        if old_type == VoteType.UP:
            story.vote_score -= 1
        else:
            story.vote_score += 1

        if new_vote_type == VoteType.UP or new_vote_type == VoteType.UP.value:
            story.vote_score += 1
        else:
            story.vote_score -= 1

    await db.commit()
    await db.refresh(existing_vote)
    return existing_vote


async def delete_vote(db: AsyncSession, vote: Vote) -> None:
    """Remove a vote and reverse its effect on vote_score."""
    story = await get_story_part_by_id(db, str(vote.story_part_id))
    if story:
        if vote.vote_type == VoteType.UP:
            story.vote_score -= 1
        else:
            story.vote_score += 1

    await db.delete(vote)
    await db.commit()


async def build_story_tree(
    db: AsyncSession,
    root_id: str,
    include_quarantined: bool = False,
    max_depth: int = 50,
) -> StoryPartTree | None:
    """
    Build a recursive tree of story parts starting from root_id.

    Args:
        db: Database session.
        root_id: UUID of the root story part.
        include_quarantined: Whether to include quarantined parts.
        max_depth: Safety limit to prevent unbounded recursion.

    Returns:
        Nested StoryPartTree or None if the root does not exist.
    """
    root = await get_story_part_by_id(db, root_id)
    if not root:
        return None
    if root.is_quarantined and not include_quarantined:
        return None

    async def _build(part: StoryPart, depth: int) -> StoryPartTree:
        children_count = await get_children_count(db, str(part.id))
        node = StoryPartTree(
            id=part.id,
            teaser=part.teaser,
            content=part.content,
            parent_part_id=part.parent_part_id,
            author_id=part.author_id,
            vote_score=part.vote_score,
            recursive_score=part.recursive_score,
            is_quarantined=part.is_quarantined,
            quarantine_reason=part.quarantine_reason,
            depth_level=part.depth_level,
            created_at=part.created_at,
            updated_at=part.updated_at,
            author_username=part.author.username if part.author else None,
            children_count=children_count,
            children=[],
        )
        if depth >= max_depth:
            return node

        children = await get_story_children(
            db, str(part.id), include_quarantined=include_quarantined
        )
        node.children = [await _build(child, depth + 1) for child in children]
        return node

    return await _build(root, 0)
