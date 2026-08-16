"""organizations and teams

Revision ID: 005_organizations_and_teams
Revises: 004_saas_auth_tables
Create Date: 2026-08-06 05:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005_organizations_and_teams'
down_revision = '004_saas_auth_tables'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('logo_url', sa.String(), nullable=True),
        sa.Column('primary_color', sa.String(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_organizations_id', 'organizations', ['id'], unique=False)
    op.create_index('ix_organizations_slug', 'organizations', ['slug'], unique=True)

    # Create memberships table
    op.create_table(
        'memberships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(), server_default='Member', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_memberships_id', 'memberships', ['id'], unique=False)
    op.create_index('ix_memberships_organization_id', 'memberships', ['organization_id'], unique=False)
    op.create_index('ix_memberships_user_id', 'memberships', ['user_id'], unique=False)
    op.create_index('ix_memberships_org_user', 'memberships', ['organization_id', 'user_id'], unique=True)

    # Create invitations table
    op.create_table(
        'invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('role', sa.String(), server_default='Member', nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('status', sa.String(), server_default='pending', nullable=False),
        sa.Column('invited_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_invitations_id', 'invitations', ['id'], unique=False)
    op.create_index('ix_invitations_organization_id', 'invitations', ['organization_id'], unique=False)
    op.create_index('ix_invitations_email', 'invitations', ['email'], unique=False)
    op.create_index('ix_invitations_token', 'invitations', ['token'], unique=True)

    # Create organization_audit_events table
    op.create_table(
        'organization_audit_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_org_audit_id', 'organization_audit_events', ['id'], unique=False)
    op.create_index('ix_org_audit_organization_id', 'organization_audit_events', ['organization_id'], unique=False)

def downgrade() -> None:
    op.drop_table('organization_audit_events')
    op.drop_table('invitations')
    op.drop_table('memberships')
    op.drop_table('organizations')
