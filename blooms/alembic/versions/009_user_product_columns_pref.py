"""User preference: visible columns in product list

Revision ID: 009
Revises: 008
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("products_columns_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "products_columns_json")
