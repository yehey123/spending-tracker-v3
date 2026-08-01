"""Add users, oauth_accounts, refresh_tokens tables for E12 auth."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True),
                  server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=True),
        sa.Column('password_hash', sa.Text(), nullable=True),   # NULL = Google-only account
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )

    op.create_table(
        'oauth_accounts',
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('provider_sub', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('provider', 'provider_sub'),
    )

    op.create_table(
        'refresh_tokens',
        sa.Column('token_hash', sa.Text(), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('rotated_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_table('oauth_accounts')
    op.drop_table('users')
