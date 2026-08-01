"""E22 Story 22.3: drop storage_key column from statements (always-NULL, write-only)."""

from alembic import op

revision = '0016'
down_revision = '0015'


def upgrade():
    op.drop_column('statements', 'storage_key')


def downgrade():
    import sqlalchemy as sa
    op.add_column(
        'statements',
        sa.Column('storage_key', sa.String(512), nullable=True),
    )
