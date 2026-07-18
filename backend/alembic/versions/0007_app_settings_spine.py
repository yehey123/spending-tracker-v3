"""app_settings spine: review_before_commit, confidence thresholds

NOTE: home_currency column was added in 0004 — skipped here to avoid duplicate column error.
"""

from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('app_settings', sa.Column('review_before_commit', sa.Boolean(),
                  nullable=False, server_default='true'))
    op.add_column('app_settings', sa.Column('ai_category_confidence_auto', sa.Float(),
                  nullable=False, server_default='0.85'))
    op.add_column('app_settings', sa.Column('ai_category_confidence_suggest', sa.Float(),
                  nullable=False, server_default='0.50'))


def downgrade() -> None:
    for col in ('ai_category_confidence_suggest', 'ai_category_confidence_auto',
                'review_before_commit'):
        op.drop_column('app_settings', col)
