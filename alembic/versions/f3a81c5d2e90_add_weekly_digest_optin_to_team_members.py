"""add_weekly_digest_optin_to_team_members

Revision ID: f3a81c5d2e90
Revises: d91648dc4f04
Create Date: 2026-06-09 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a81c5d2e90'
down_revision: Union[str, None] = 'd91648dc4f04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add weekly_digest_optin field to team_members table (WOF-10).

    Existing members default to opted OUT — the Monday digest previously
    went only to the escalation contacts (settings-based name/phone pairs),
    so no team member loses a digest they were receiving. Escalation
    contacts keep receiving it via their per-contact settings flags, which
    default to enabled.
    """
    op.add_column(
        'team_members',
        sa.Column(
            'weekly_digest_optin',
            sa.Boolean(),
            nullable=False,
            server_default='0'
        )
    )


def downgrade() -> None:
    """Remove weekly_digest_optin field from team_members table."""
    op.drop_column('team_members', 'weekly_digest_optin')
