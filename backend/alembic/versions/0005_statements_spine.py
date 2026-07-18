"""statements spine: file_type, declared_total, raw_ocr_text, markdown_content,
   parse_errors, categorization_confidence, new status values"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('statements', sa.Column('file_type', sa.String(20), nullable=False,
                  server_default='statement'))
    op.add_column('statements', sa.Column('declared_total', sa.Numeric(14, 4), nullable=True))
    op.add_column('statements', sa.Column('raw_ocr_text', sa.Text(), nullable=True))
    op.add_column('statements', sa.Column('markdown_content', sa.Text(), nullable=True))
    op.add_column('statements', sa.Column('parse_errors', postgresql.JSONB(), nullable=True))
    op.add_column('statements', sa.Column('categorization_confidence', sa.Float(), nullable=True))

    # ALTER TYPE ADD VALUE cannot run inside a transaction in PG 12+
    with op.get_context().autocommit_block():
        for val in ('pending', 'ocr_failed', 'parse_failed', 'pending_categorization',
                    'staged', 'committed', 'discarded', 'expired', 'error'):
            op.execute(f"ALTER TYPE statement_status ADD VALUE IF NOT EXISTS '{val}'")


def downgrade() -> None:
    # ENUM value removal is unsupported in PG without full type rebuild
    op.drop_column('statements', 'categorization_confidence')
    op.drop_column('statements', 'parse_errors')
    op.drop_column('statements', 'markdown_content')
    op.drop_column('statements', 'raw_ocr_text')
    op.drop_column('statements', 'declared_total')
    op.drop_column('statements', 'file_type')
