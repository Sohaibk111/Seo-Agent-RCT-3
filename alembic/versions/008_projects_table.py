"""projects table

Revision ID: 008_projects_table
Revises: 007_auth_security_hardening
Create Date: 2026-08-06 10:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008_projects_table'
down_revision = '007_auth_security_hardening'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), server_default='active', nullable=False),
        sa.Column('color', sa.String(), nullable=True),
        sa.Column('icon', sa.String(), nullable=True),
        sa.Column('timezone', sa.String(), server_default='UTC', nullable=False),
        sa.Column('language', sa.String(), server_default='en', nullable=False),
        sa.Column('settings', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_projects_id', 'projects', ['id'], unique=False)
    op.create_index('ix_projects_organization_id', 'projects', ['organization_id'], unique=False)
    op.create_index('ix_projects_owner_id', 'projects', ['owner_id'], unique=False)
    op.create_index('ix_projects_slug', 'projects', ['slug'], unique=False)
    op.create_index('ix_projects_org_slug', 'projects', ['organization_id', 'slug'], unique=True)
    op.create_index('ix_projects_org_archived', 'projects', ['organization_id', 'archived'], unique=False)
    op.create_index('ix_projects_org_status', 'projects', ['organization_id', 'status'], unique=False)

def downgrade() -> None:
    op.drop_index('ix_projects_org_status', table_name='projects')
    op.drop_index('ix_projects_org_archived', table_name='projects')
    op.drop_index('ix_projects_org_slug', table_name='projects')
    op.drop_index('ix_projects_slug', table_name='projects')
    op.drop_index('ix_projects_owner_id', table_name='projects')
    op.drop_index('ix_projects_organization_id', table_name='projects')
    op.drop_index('ix_projects_id', table_name='projects')
    op.drop_table('projects')
