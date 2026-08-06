"""add saas auth tables and user fields

Revision ID: 004_saas_auth_tables
Revises: 003_perf_indexes
Create Date: 2026-08-06 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_saas_auth_tables'
down_revision = '003_perf_indexes'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add SaaS fields to users table
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('avatar_url', sa.String(), nullable=True))
    op.add_column('users', sa.Column('timezone', sa.String(), server_default='UTC', nullable=False))
    op.add_column('users', sa.Column('language', sa.String(), server_default='en', nullable=False))
    op.add_column('users', sa.Column('notification_settings', sa.JSON(), nullable=True))

    # Create user_sessions table
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_token', sa.String(), nullable=False),
        sa.Column('refresh_token', sa.String(), nullable=False),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('remember_me', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_sessions_id', 'user_sessions', ['id'], unique=False)
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'], unique=False)
    op.create_index('ix_user_sessions_session_token', 'user_sessions', ['session_token'], unique=True)
    op.create_index('ix_user_sessions_refresh_token', 'user_sessions', ['refresh_token'], unique=True)
    op.create_index('ix_user_sessions_user_active', 'user_sessions', ['user_id', 'is_active'], unique=False)

    # Create password_reset_tokens table
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('is_used', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_password_reset_tokens_id', 'password_reset_tokens', ['id'], unique=False)
    op.create_index('ix_password_reset_tokens_user_id', 'password_reset_tokens', ['user_id'], unique=False)
    op.create_index('ix_password_reset_tokens_token', 'password_reset_tokens', ['token'], unique=True)

    # Create email_verification_tokens table
    op.create_table(
        'email_verification_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('is_used', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_email_verification_tokens_id', 'email_verification_tokens', ['id'], unique=False)
    op.create_index('ix_email_verification_tokens_user_id', 'email_verification_tokens', ['user_id'], unique=False)
    op.create_index('ix_email_verification_tokens_token', 'email_verification_tokens', ['token'], unique=True)

def downgrade() -> None:
    op.drop_table('email_verification_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_table('user_sessions')
    op.drop_column('users', 'notification_settings')
    op.drop_column('users', 'language')
    op.drop_column('users', 'timezone')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'is_verified')
