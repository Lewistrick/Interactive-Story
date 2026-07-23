"""Unit tests for story CRUD and voting with a mocked database session."""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.crud import story as story_crud
from app.models.story_part import VoteType
from app.models.vote import Vote
from app.schemas.story import StoryPartCreate


def _make_story(
    *,
    story_id=None,
    parent_id=None,
    author_id=None,
    depth=0,
    vote_score=0,
    username="alice",
    teaser="Teaser",
    content="Content",
):
    """Build a lightweight story-like object for mocked CRUD tests."""
    author = SimpleNamespace(username=username) if username else None
    return SimpleNamespace(
        id=story_id or uuid4(),
        parent_part_id=parent_id,
        author_id=author_id or uuid4(),
        teaser=teaser,
        content=content,
        vote_score=vote_score,
        recursive_score=0,
        is_quarantined=False,
        quarantine_reason=None,
        depth_level=depth,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        author=author,
    )


def _make_db() -> AsyncMock:
    """Async SQLAlchemy session mock."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.delete = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_create_root_story_sets_depth_zero():
    """Root stories get depth_level 0."""
    db = _make_db()
    author_id = str(uuid4())
    payload = StoryPartCreate(teaser="Hello", content="World begins.")

    created = await story_crud.create_story_part(db, payload, author_id)

    db.add.assert_called_once()
    db.commit.assert_awaited()
    db.refresh.assert_awaited()
    assert created.depth_level == 0
    assert created.author_id == author_id
    assert created.parent_part_id is None


@pytest.mark.asyncio
async def test_create_continuation_increments_depth():
    """Continuations inherit parent depth + 1."""
    db = _make_db()
    parent = _make_story(depth=2)
    author_id = str(uuid4())
    payload = StoryPartCreate(
        teaser="Next",
        content="Continued.",
        parent_part_id=parent.id,
    )

    with patch.object(story_crud, "get_story_part_by_id", AsyncMock(return_value=parent)):
        created = await story_crud.create_story_part(db, payload, author_id)

    assert created.depth_level == 3
    assert created.parent_part_id == parent.id


@pytest.mark.asyncio
async def test_create_vote_upvote_increments_score():
    """Creating an upvote increments vote_score by 1."""
    db = _make_db()
    story = _make_story(vote_score=0)
    user_id = str(uuid4())

    with patch.object(story_crud, "get_story_part_by_id", AsyncMock(return_value=story)):
        vote = await story_crud.create_vote(db, str(story.id), user_id, VoteType.UP)

    assert story.vote_score == 1
    assert vote.vote_type == VoteType.UP
    db.add.assert_called_once()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_create_vote_downvote_decrements_score():
    """Creating a downvote decrements vote_score by 1."""
    db = _make_db()
    story = _make_story(vote_score=0)
    user_id = str(uuid4())

    with patch.object(story_crud, "get_story_part_by_id", AsyncMock(return_value=story)):
        await story_crud.create_vote(db, str(story.id), user_id, VoteType.DOWN)

    assert story.vote_score == -1


@pytest.mark.asyncio
async def test_update_vote_switches_up_to_down():
    """Switching UP → DOWN adjusts score by -2."""
    db = _make_db()
    story = _make_story(vote_score=1)
    existing = SimpleNamespace(
        vote_type=VoteType.UP,
        story_part_id=story.id,
        user_id=uuid4(),
    )

    with patch.object(story_crud, "get_story_part_by_id", AsyncMock(return_value=story)):
        await story_crud.update_vote(db, cast(Vote, existing), VoteType.DOWN)

    assert existing.vote_type == VoteType.DOWN
    assert story.vote_score == -1


@pytest.mark.asyncio
async def test_delete_vote_reverses_upvote():
    """Removing an upvote decrements vote_score."""
    db = _make_db()
    story = _make_story(vote_score=1)
    vote = SimpleNamespace(vote_type=VoteType.UP, story_part_id=story.id)

    with patch.object(story_crud, "get_story_part_by_id", AsyncMock(return_value=story)):
        await story_crud.delete_vote(db, cast(Vote, vote))

    assert story.vote_score == 0
    db.delete.assert_awaited_with(vote)


@pytest.mark.asyncio
async def test_get_story_children_orders_by_vote_score_then_created_at():
    """Children query orders by vote_score desc, then created_at desc."""
    db = _make_db()
    parent_id = str(uuid4())
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)

    await story_crud.get_story_children(db, parent_id)

    assert db.execute.await_args is not None
    stmt = db.execute.await_args.args[0]
    order_sql = [str(clause) for clause in stmt._order_by_clauses]
    assert order_sql[0] == "story_parts.vote_score DESC"
    assert order_sql[1] == "story_parts.created_at DESC"


@pytest.mark.asyncio
async def test_build_story_tree_nests_children():
    """Tree builder nests children recursively under the root."""
    db = _make_db()
    root = _make_story(teaser="Root")
    child = _make_story(parent_id=root.id, teaser="Child", depth=1)
    grandchild = _make_story(parent_id=child.id, teaser="Grand", depth=2)

    async def fake_get_by_id(_db, story_id):
        mapping = {str(root.id): root, str(child.id): child, str(grandchild.id): grandchild}
        return mapping.get(str(story_id))

    async def fake_children(_db, parent_id, include_quarantined=False):
        by_parent = {
            str(root.id): [child],
            str(child.id): [grandchild],
            str(grandchild.id): [],
        }
        return by_parent.get(str(parent_id), [])

    with (
        patch.object(story_crud, "get_story_part_by_id", side_effect=fake_get_by_id),
        patch.object(story_crud, "get_story_children", side_effect=fake_children),
        patch.object(story_crud, "get_children_count", AsyncMock(side_effect=[1, 1, 0])),
    ):
        tree = await story_crud.build_story_tree(db, str(root.id))

    assert tree is not None
    assert tree.teaser == "Root"
    assert len(tree.children) == 1
    assert tree.children[0].teaser == "Child"
    assert len(tree.children[0].children) == 1
    assert tree.children[0].children[0].teaser == "Grand"


@pytest.mark.asyncio
async def test_build_story_tree_missing_root_returns_none():
    """Missing root yields None."""
    db = _make_db()
    with patch.object(story_crud, "get_story_part_by_id", AsyncMock(return_value=None)):
        tree = await story_crud.build_story_tree(db, str(uuid4()))
    assert tree is None
