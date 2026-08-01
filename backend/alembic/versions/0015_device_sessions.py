"""E19: session_id + device_name on refresh_tokens for device/session management."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0015'
down_revision = '0014'


def upgrade():
    op.add_column(
        'refresh_tokens',
        sa.Column(
            'session_id',
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.execute("UPDATE refresh_tokens SET session_id = gen_random_uuid() WHERE session_id IS NULL")
    op.alter_column('refresh_tokens', 'session_id', nullable=False)
    op.create_index('ix_refresh_tokens_session_id', 'refresh_tokens', ['session_id'])

    op.add_column(
        'refresh_tokens',
        sa.Column('device_name', sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column('refresh_tokens', 'device_name')
    op.drop_index('ix_refresh_tokens_session_id', table_name='refresh_tokens')
    op.drop_column('refresh_tokens', 'session_id')
