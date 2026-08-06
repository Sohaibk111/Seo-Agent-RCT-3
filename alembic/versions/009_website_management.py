"""website management table updates

Revision ID: 009_website_management
Revises: 008_projects_table
Create Date: 2026-08-06 11:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '009_website_management'
down_revision = '008_projects_table'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add columns to websites table
    op.add_column('websites', sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True))
    op.add_column('websites', sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True))
    op.add_column('websites', sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
    op.add_column('websites', sa.Column('normalized_domain', sa.String(), nullable=True))
    op.add_column('websites', sa.Column('protocol', sa.String(), server_default='https', nullable=True))
    op.add_column('websites', sa.Column('status', sa.String(), server_default='active', nullable=True))
    op.add_column('websites', sa.Column('verification_status', sa.String(), server_default='unverified', nullable=True))
    op.add_column('websites', sa.Column('favicon', sa.String(), nullable=True))
    op.add_column('websites', sa.Column('country', sa.String(), nullable=True))
    op.add_column('websites', sa.Column('language', sa.String(), server_default='en', nullable=True))
    op.add_column('websites', sa.Column('timezone', sa.String(), server_default='UTC', nullable=True))
    op.add_column('websites', sa.Column('settings', sa.JSON(), server_default='{}', nullable=True))
    op.add_column('websites', sa.Column('last_scan_at', sa.DateTime(), nullable=True))
    op.add_column('websites', sa.Column('archived', sa.Boolean(), server_default=sa.text('false'), nullable=True))
    op.add_column('websites', sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True))

    # Create indexes
    op.create_index('ix_websites_project_id', 'websites', ['project_id'], unique=False)
    op.create_index('ix_websites_organization_id', 'websites', ['organization_id'], unique=False)
    op.create_index('ix_websites_owner_id', 'websites', ['owner_id'], unique=False)
    op.create_index('ix_websites_domain', 'websites', ['domain'], unique=False)
    op.create_index('ix_websites_normalized_domain', 'websites', ['normalized_domain'], unique=False)
    op.create_index('ix_websites_org_normalized_domain', 'websites', ['organization_id', 'normalized_domain'], unique=True)
    op.create_index('ix_websites_project_archived', 'websites', ['project_id', 'archived'], unique=False)
    op.create_index('ix_websites_org_archived', 'websites', ['organization_id', 'archived'], unique=False)

def downgrade() -> None:
    op.drop_index('ix_websites_org_archived', table_name='websites')
    op.drop_index('ix_websites_project_archived', table_name='websites')
    op.drop_index('ix_websites_org_normalized_domain', table_name='websites')
    op.drop_index('ix_websites_normalized_domain', table_name='websites')
    op.drop_index('ix_websites_domain', table_name='websites')
    op.drop_index('ix_websites_owner_id', table_name='websites')
    op.drop_index('ix_websites_organization_id', table_name='websites')
    op.drop_index('ix_websites_project_id', table_name='websites')

    op.drop_column('websites', 'updated_at')
    op.drop_column('websites', 'archived')
    op.drop_column('websites', 'last_scan_at')
    op.drop_column('websites', 'settings')
    op.drop_column('websites', 'timezone')
    op.drop_column('websites', 'language')
    op.drop_column('websites', 'country')
    op.drop_column('websites', 'favicon')
    op.drop_column('websites', 'verification_status')
    op.drop_column('websites', 'status')
    op.drop_column('websites', 'protocol')
    op.drop_column('websites', 'normalized_domain')
    op.drop_column('websites', 'owner_id')
    op.drop_column('websites', 'organization_id')
    op.drop_column('websites', 'project_id')
