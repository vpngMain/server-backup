"""Adresa provozovny u odběratele (pokud se liší od sídla)

Revision ID: 005
Revises: 004
Create Date: 2025-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("provozovna_street", sa.String(300), nullable=True))
    op.add_column("customers", sa.Column("provozovna_city", sa.String(100), nullable=True))
    op.add_column("customers", sa.Column("provozovna_zip_code", sa.String(20), nullable=True))
    op.add_column("customers", sa.Column("provozovna_country", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "provozovna_country")
    op.drop_column("customers", "provozovna_zip_code")
    op.drop_column("customers", "provozovna_city")
    op.drop_column("customers", "provozovna_street")
