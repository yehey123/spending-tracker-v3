"""categories spine: parent_id, slug, is_system"""

from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('categories', sa.Column('parent_id',
                  sa.Integer(), sa.ForeignKey('categories.id', ondelete='RESTRICT'),
                  nullable=True))
    op.add_column('categories', sa.Column('slug', sa.String(100), nullable=True))
    op.add_column('categories', sa.Column('is_system', sa.Boolean(),
                  nullable=False, server_default='false'))
    op.create_unique_constraint('uq_categories_slug', 'categories', ['slug'])


def downgrade() -> None:
    op.drop_constraint('uq_categories_slug', 'categories', type_='unique')
    op.drop_column('categories', 'is_system')
    op.drop_column('categories', 'slug')
    op.drop_column('categories', 'parent_id')
