"""Add indexes for FK and status

Revision ID: 002
Revises: 001
Create Date: 2025-03-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_import_files_import_batch_id", "import_files", ["import_batch_id"], unique=False)
    op.create_index("ix_import_rows_import_file_id", "import_rows", ["import_file_id"], unique=False)
    op.create_index("ix_delivery_notes_customer_id", "delivery_notes", ["customer_id"], unique=False)
    op.create_index("ix_delivery_notes_status", "delivery_notes", ["status"], unique=False)
    op.create_index("ix_delivery_note_items_delivery_note_id", "delivery_note_items", ["delivery_note_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_delivery_note_items_delivery_note_id", table_name="delivery_note_items")
    op.drop_index("ix_delivery_notes_status", table_name="delivery_notes")
    op.drop_index("ix_delivery_notes_customer_id", table_name="delivery_notes")
    op.drop_index("ix_import_rows_import_file_id", table_name="import_rows")
    op.drop_index("ix_import_files_import_batch_id", table_name="import_files")
