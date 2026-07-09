"""run status enum

Revision ID: 0002_run_status_enum
Revises: 0001_initial
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002_run_status_enum'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    coding_run_status = postgresql.ENUM('DRAFT', 'REVIEWED', 'APPLIED', name='coding_run_status')
    coding_run_status.create(op.get_bind(), checkfirst=True)

    # Existing rows hold the old plain-string default 'draft'; the new native
    # enum stores Python enum *names* (uppercase), matching how coding_run_kind
    # already works (see CodingRunKind: value='s2', DB label='S2').
    op.execute("UPDATE coding_runs SET status = upper(status)")
    op.alter_column(
        'coding_runs', 'status',
        existing_type=sa.String(length=32),
        type_=coding_run_status,
        postgresql_using='status::coding_run_status',
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'coding_runs', 'status',
        existing_type=postgresql.ENUM('DRAFT', 'REVIEWED', 'APPLIED', name='coding_run_status'),
        type_=sa.String(length=32),
        postgresql_using='status::text',
        nullable=False,
    )
    op.execute("UPDATE coding_runs SET status = lower(status)")

    # Native Postgres ENUM types outlive their tables/columns (ALTER COLUMN
    # away from the type doesn't drop it). Without this, a second
    # `upgrade head` after `downgrade base` fails with "type already exists".
    sa.Enum(name='coding_run_status').drop(op.get_bind(), checkfirst=True)
