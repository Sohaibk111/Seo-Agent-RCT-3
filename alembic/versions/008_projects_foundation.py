"""projects foundation

Revision ID: 008_projects_foundation
Revises: 007_auth_security_hardening
Create Date: 2026-08-06 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008_projects_foundation'
down_revision = '007_auth_security_hardening'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='active', nullable=False),
        sa.Column('color', sa.String(length=50), server_default='#3B82F6', nullable=True),
        sa.Column('icon', sa.String(length=50), server_default='folder', nullable=True),
        sa.Column('timezone', sa.String(length=50), server_default='UTC', nullable=False),
        sa.Column('language', sa.String(length=10), server_default='en', nullable=False),
        sa.Column('settings', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('archived', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False)
    )

    # 2. Create required indexes and constraints
    op.create_index('ix_projects_organization_id', 'projects', ['organization_id'])
    op.create_index('ix_projects_owner_id', 'projects', ['owner_id'])
    op.create_index('ix_projects_slug', 'projects', ['slug'])
    op.create_index('ix_projects_org_slug', 'projects', ['organization_id', 'slug'], unique=True)
    op.create_index('ix_projects_org_archived', 'projects', ['organization_id', 'archived'])
    op.create_index('ix_projects_org_status', 'projects', ['organization_id', 'status'])
    op.create_index('ix_projects_created_at', 'projects', ['created_at'])

def downgrade() -> None:
    op.drop_index('ix_projects_created_at', table_name='projects')
    op.drop_index('ix_projects_org_status', table_name='projects')
    op.drop_index('ix_projects_org_archived', table_name='projects')
    op.drop_index('ix_projects_org_slug', table_name='projects')
    op.drop_index('ix_projects_slug', table_name='projects')
    op.drop_index('ix_projects_owner_id', table_name='projects')
    op.drop_index('ix_projects_organization_id', table_name='projects')
    op.drop_table('projects')
