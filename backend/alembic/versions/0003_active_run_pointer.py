"""active run pointer

Revision ID: 0003_active_run_pointer
Revises: 0002_run_status_enum
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003_active_run_pointer'
down_revision: Union[str, None] = '0002_run_status_enum'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('questions', sa.Column('active_run_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_questions_active_run_id_coding_runs', 'questions', 'coding_runs',
        ['active_run_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_questions_active_run_id_coding_runs', 'questions', type_='foreignkey')
    op.drop_column('questions', 'active_run_id')
