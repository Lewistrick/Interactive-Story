"""Story and voting API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_current_user_optional
from app.core.rate_limit import enforce_rate_limit
from app.crud.report import count_reports_for_part, create_report, get_user_report
from app.crud.story import (
    build_story_tree,
    create_story_part,
    create_vote,
    delete_vote,
    get_children_count,
    get_root_stories,
    get_story_children,
    get_story_part_by_id,
    get_user_vote,
    update_vote,
)
from app.db.session import get_db
from app.models.story_part import VoteType
from app.models.user import User
from app.schemas.moderation import ReportCreate, ReportResponse
from app.schemas.story import (
    StoryListResponse,
    StoryPartCreate,
    StoryPartResponse,
    StoryPartTree,
    VoteActionResponse,
    VoteCreate,
)
from app.services.content_validation import validate_story_content
from app.services.quarantine import (
    assert_story_visible,
    enforce_user_not_quarantined,
    evaluate_rapid_posting_quarantine,
    quarantine_story_part,
)
from app.services.reputation import (
    enforce_create_limits,
    enforce_vote_limits,
    record_part_created,
)
from app.services.scoring import refresh_scores_after_vote

router = APIRouter()


async def _to_story_response(
    db: AsyncSession,
    story,
    user_vote: Optional[VoteType] = None,
) -> StoryPartResponse:
    """Map a StoryPart ORM object to a StoryPartResponse."""
    children_count = await get_children_count(db, str(story.id))
    return StoryPartResponse(
        id=story.id,
        teaser=story.teaser,
        content=story.content,
        parent_part_id=story.parent_part_id,
        author_id=story.author_id,
        vote_score=story.vote_score,
        recursive_score=story.recursive_score,
        is_quarantined=story.is_quarantined,
        quarantine_reason=story.quarantine_reason,
        depth_level=story.depth_level,
        created_at=story.created_at,
        updated_at=story.updated_at,
        author_username=story.author.username if story.author else None,
        children_count=children_count,
        user_vote=user_vote,
    )


@router.get("/", response_model=list[StoryListResponse])
async def list_root_stories(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all root stories (story beginnings)."""
    stories = await get_root_stories(db, skip=skip, limit=limit)

    result = []
    for story in stories:
        children_count = await get_children_count(db, str(story.id))
        result.append(
            StoryListResponse(
                id=story.id,
                teaser=story.teaser,
                author_id=story.author_id,
                vote_score=story.vote_score,
                recursive_score=story.recursive_score,
                created_at=story.created_at,
                author_username=story.author.username if story.author else None,
                children_count=children_count,
            )
        )

    return result


@router.get("/{story_id}", response_model=StoryPartResponse)
async def get_story_part(
    story_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get a specific story part by ID."""
    story = await get_story_part_by_id(db, str(story_id))
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story part not found",
        )
    assert_story_visible(story, current_user)

    user_vote = None
    if current_user:
        existing = await get_user_vote(db, str(story_id), str(current_user.id))
        if existing:
            user_vote = existing.vote_type

    return await _to_story_response(db, story, user_vote=user_vote)


@router.get("/{story_id}/children", response_model=list[StoryPartResponse])
async def get_story_part_children(
    story_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get all continuations (children) of a story part."""
    parent = await get_story_part_by_id(db, str(story_id))
    if not parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent story part not found",
        )
    assert_story_visible(parent, current_user)

    include_quarantined = bool(current_user and current_user.is_moderator)
    children = await get_story_children(db, str(story_id), include_quarantined=include_quarantined)
    return [await _to_story_response(db, child) for child in children]


@router.get("/{story_id}/tree", response_model=StoryPartTree)
async def get_story_tree(
    story_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get the full subtree rooted at a story part."""
    root = await get_story_part_by_id(db, str(story_id))
    if not root:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story part not found",
        )
    assert_story_visible(root, current_user)

    include_quarantined = bool(current_user and current_user.is_moderator)
    tree = await build_story_tree(db, str(story_id), include_quarantined=include_quarantined)
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story part not found",
        )
    return tree


@router.post(
    "/",
    response_model=StoryPartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_root_story(
    story: StoryPartCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new root story (beginning of a story tree)."""
    await enforce_rate_limit(
        request,
        bucket="write",
        limit=settings.RATE_LIMIT_WRITE_MAX,
        user_id=str(current_user.id),
    )
    enforce_user_not_quarantined(current_user)
    await enforce_create_limits(db, current_user, story.teaser, story.content, parent_id=None)
    content_check = await validate_story_content(db, current_user, story.teaser, story.content)
    story_data = story.model_copy(update={"parent_part_id": None})
    db_story = await create_story_part(db, story_data, str(current_user.id))
    await record_part_created(db, str(current_user.id))
    if content_check.should_quarantine:
        await quarantine_story_part(
            db,
            db_story,
            reason=(
                f"spam_confidence {content_check.spam_confidence:.2f} >= "
                f"{settings.QUARANTINE_SPAM_CONFIDENCE}"
            ),
            triggered_by="content_spam",
        )
    await evaluate_rapid_posting_quarantine(db, str(current_user.id))
    background_tasks.add_task(
        refresh_scores_after_vote,
        str(db_story.id),
        str(current_user.id),
    )
    db_story = await get_story_part_by_id(db, str(db_story.id))
    return await _to_story_response(db, db_story)


@router.post(
    "/{story_id}/continue",
    response_model=StoryPartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def continue_story(
    story_id: UUID,
    story: StoryPartCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a continuation of an existing story part."""
    await enforce_rate_limit(
        request,
        bucket="write",
        limit=settings.RATE_LIMIT_WRITE_MAX,
        user_id=str(current_user.id),
    )
    enforce_user_not_quarantined(current_user)
    parent = await get_story_part_by_id(db, str(story_id))
    if not parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent story part not found",
        )
    assert_story_visible(parent, current_user)

    await enforce_create_limits(db, current_user, story.teaser, story.content, parent_id=story_id)
    content_check = await validate_story_content(db, current_user, story.teaser, story.content)
    story_data = story.model_copy(update={"parent_part_id": story_id})
    db_story = await create_story_part(db, story_data, str(current_user.id))
    await record_part_created(db, str(current_user.id))
    if content_check.should_quarantine:
        await quarantine_story_part(
            db,
            db_story,
            reason=(
                f"spam_confidence {content_check.spam_confidence:.2f} >= "
                f"{settings.QUARANTINE_SPAM_CONFIDENCE}"
            ),
            triggered_by="content_spam",
        )
    await evaluate_rapid_posting_quarantine(db, str(current_user.id))
    background_tasks.add_task(
        refresh_scores_after_vote,
        str(db_story.id),
        str(current_user.id),
    )
    db_story = await get_story_part_by_id(db, str(db_story.id))
    return await _to_story_response(db, db_story)


@router.post(
    "/{story_id}/vote",
    response_model=VoteActionResponse,
)
async def vote_on_story(
    story_id: UUID,
    vote: VoteCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Vote on a story part (upvote or downvote).

    Clicking the same vote type again removes the vote (toggle off).
    Creating or changing a vote requires meeting the reputation vote gate.
    """
    await enforce_rate_limit(
        request,
        bucket="write",
        limit=settings.RATE_LIMIT_WRITE_MAX,
        user_id=str(current_user.id),
    )
    enforce_user_not_quarantined(current_user)
    story = await get_story_part_by_id(db, str(story_id))
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story part not found",
        )
    assert_story_visible(story, current_user)

    author_id = str(story.author_id)
    existing_vote = await get_user_vote(db, str(story_id), str(current_user.id))

    if existing_vote:
        if existing_vote.vote_type == vote.vote_type:
            await delete_vote(db, existing_vote)
            background_tasks.add_task(refresh_scores_after_vote, str(story_id), author_id)
            story = await get_story_part_by_id(db, str(story_id))
            return VoteActionResponse(
                story_part_id=story_id,
                removed=True,
                vote_score=story.vote_score if story else 0,
            )

        await enforce_vote_limits(db, current_user)
        updated_vote = await update_vote(db, existing_vote, vote.vote_type)
        background_tasks.add_task(refresh_scores_after_vote, str(story_id), author_id)
        story = await get_story_part_by_id(db, str(story_id))
        return VoteActionResponse(
            id=updated_vote.id,
            user_id=updated_vote.user_id,
            story_part_id=updated_vote.story_part_id,
            vote_type=updated_vote.vote_type,
            created_at=updated_vote.created_at,
            removed=False,
            vote_score=story.vote_score if story else 0,
        )

    await enforce_vote_limits(db, current_user)
    new_vote = await create_vote(db, str(story_id), str(current_user.id), vote.vote_type)
    background_tasks.add_task(refresh_scores_after_vote, str(story_id), author_id)
    story = await get_story_part_by_id(db, str(story_id))
    return VoteActionResponse(
        id=new_vote.id,
        user_id=new_vote.user_id,
        story_part_id=new_vote.story_part_id,
        vote_type=new_vote.vote_type,
        created_at=new_vote.created_at,
        removed=False,
        vote_score=story.vote_score if story else 0,
    )


@router.delete("/{story_id}/vote", response_model=VoteActionResponse)
async def remove_vote(
    story_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove user's vote from a story part (no reputation gate required)."""
    enforce_user_not_quarantined(current_user)
    existing_vote = await get_user_vote(db, str(story_id), str(current_user.id))
    if not existing_vote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vote not found",
        )

    story = await get_story_part_by_id(db, str(story_id))
    author_id = str(story.author_id) if story else str(current_user.id)

    await delete_vote(db, existing_vote)
    background_tasks.add_task(refresh_scores_after_vote, str(story_id), author_id)
    story = await get_story_part_by_id(db, str(story_id))
    return VoteActionResponse(
        story_part_id=story_id,
        removed=True,
        vote_score=story.vote_score if story else 0,
    )


@router.post(
    "/{story_id}/report",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def report_story_part(
    story_id: UUID,
    body: ReportCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Report a story part; auto-quarantines when enough distinct reports accumulate."""
    await enforce_rate_limit(
        request,
        bucket="write",
        limit=settings.RATE_LIMIT_WRITE_MAX,
        user_id=str(current_user.id),
    )
    enforce_user_not_quarantined(current_user)
    story = await get_story_part_by_id(db, str(story_id))
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story part not found",
        )
    assert_story_visible(story, current_user)

    existing = await get_user_report(db, str(story_id), str(current_user.id))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reported this story part",
        )

    report = await create_report(
        db,
        story_part_id=str(story_id),
        reporter_id=str(current_user.id),
        reason=body.reason,
    )
    report_count = await count_reports_for_part(db, str(story_id))
    quarantined = story.is_quarantined
    if report_count >= settings.QUARANTINE_MIN_REPORTS and not story.is_quarantined:
        await quarantine_story_part(
            db,
            story,
            reason=f"user_reports: {report_count} reports",
            triggered_by="user_reports",
        )
        quarantined = True

    return ReportResponse(
        id=report.id,
        story_part_id=report.story_part_id,
        reporter_id=report.reporter_id,
        reason=report.reason,
        created_at=report.created_at,
        quarantined=quarantined,
        report_count=report_count,
    )
