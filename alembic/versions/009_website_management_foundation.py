"""website management foundation

Revision ID: 009_website_management_foundation
Revises: 008_projects_foundation
Create Date: 2026-08-06 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '009_website_management_foundation'
down_revision = '008_projects_foundation'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Alter websites table with batch mode for SQLite/PostgreSQL compatibility
    with op.batch_alter_table('websites', schema=None) as batch_op:
        batch_op.add_column(sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True))
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True))
        batch_op.add_column(sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=50), server_default='active', nullable=False))
        batch_op.add_column(sa.Column('settings', sa.JSON(), server_default='{}', nullable=False))
        batch_op.add_column(sa.Column('metadata', sa.JSON(), server_default='{}', nullable=False))
        batch_op.add_column(sa.Column('archived', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))

        batch_op.create_index('ix_websites_project_id', ['project_id'])
        batch_op.create_index('ix_websites_organization_id', ['organization_id'])
        batch_op.create_index('ix_websites_owner_id', ['owner_id'])
        batch_op.create_index('ix_websites_status', ['status'])
        batch_op.create_index('ix_websites_archived', ['archived'])
        batch_op.create_index('ix_websites_project_domain', ['project_id', 'domain'], unique=True)
        batch_op.create_index('ix_websites_project_archived', ['project_id', 'archived'])
        batch_op.create_index('ix_websites_project_status', ['project_id', 'status'])

def downgrade() -> None:
    with op.batch_alter_table('websites', schema=None) as batch_op:
        batch_op.drop_index('ix_websites_project_status')
        batch_op.drop_index('ix_websites_project_archived')
        batch_op.drop_index('ix_websites_project_domain')
        batch_op.drop_index('ix_websites_archived')
        batch_op.drop_index('ix_websites_status')
        batch_op.drop_index('ix_websites_owner_id')
        batch_op.drop_index('ix_websites_organization_id')
        batch_op.drop_index('ix_websites_project_id')

        batch_op.drop_column('updated_at')
        batch_op.drop_column('archived')
        batch_op.drop_column('metadata')
        batch_op.drop_column('settings')
        batch_op.drop_column('status')
        batch_op.drop_column('description')
        batch_op.drop_column('name')
        batch_op.drop_column('owner_id')
        batch_op.drop_column('organization_id')
        batch_op.drop_column('project_id')
