"""add artifact_path to report_job

Revision ID: 5761d14f53f1
Revises: a601e86ae574
Create Date: 2025-09-26 09:32:23.422669

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5761d14f53f1'
down_revision: Union[str, Sequence[str], None] = 'a601e86ae574'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "report_job",
        sa.Column(
            "artifact_path",
            sa.String(length=500),
            nullable=True
        )
    )
    # pass


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column(
        "report_job",
        "artifact_path"
    )
    # pass
