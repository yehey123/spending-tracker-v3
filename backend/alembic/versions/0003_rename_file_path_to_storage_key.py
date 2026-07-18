"""Rename statements.file_path to storage_key and strip directory prefix from existing rows

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Strip any directory prefix from existing absolute paths (e.g. /tmp/.../abc.png → abc.png)
    op.execute(
        "UPDATE statements SET file_path = regexp_replace(file_path, '^.*/', '') "
        "WHERE file_path IS NOT NULL"
    )
    op.alter_column("statements", "file_path", new_column_name="storage_key")


def downgrade() -> None:
    # Rename back — note: path prefix is NOT re-prepended (basenames remain after downgrade)
    op.alter_column("statements", "storage_key", new_column_name="file_path")
