"""E17: is_active on users, system_config table."""

from alembic import op
import sqlalchemy as sa

revision = '0013'
down_revision = '0012'


def upgrade():
    op.add_column(
        'users',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
    )

    op.create_table(
        'system_config',
        sa.Column('key', sa.Text(), primary_key=True),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )


def downgrade():
    op.drop_table('system_config')
    op.drop_column('users', 'is_active')
