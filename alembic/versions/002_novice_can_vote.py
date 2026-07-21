"""Allow Novice tier to vote (break cold-start deadlock).

Revision ID: 002_novice_can_vote
Revises: 001_initial
Create Date: 2026-07-21

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_novice_can_vote"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Set Novice can_vote_threshold to 0 so new users can vote."""
    op.execute(
        """
        UPDATE reputation_tiers
        SET can_vote_threshold = 0
        WHERE name = 'Novice'
        """
    )


def downgrade() -> None:
    """Restore Novice can_vote_threshold to 50."""
    op.execute(
        """
        UPDATE reputation_tiers
        SET can_vote_threshold = 50
        WHERE name = 'Novice'
        """
    )
