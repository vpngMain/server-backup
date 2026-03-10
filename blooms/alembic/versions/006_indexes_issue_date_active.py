"""Indexy: delivery_notes.issue_date, products.active

Revision ID: 006
Revises: 005
Create Date: 2025-03-09

"""
from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_delivery_notes_issue_date", "delivery_notes", ["issue_date"], unique=False)
    op.create_index("ix_products_active", "products", ["active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_products_active", table_name="products")
    op.drop_index("ix_delivery_notes_issue_date", table_name="delivery_notes")
