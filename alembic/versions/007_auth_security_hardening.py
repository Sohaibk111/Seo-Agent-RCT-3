"""auth security hardening

Revision ID: 007_auth_security_hardening
Revises: 006_audit_logs
Create Date: 2026-08-06 07:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007_auth_security_hardening'
down_revision = '006_audit_logs'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Add security and tracking columns to users table
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('last_login_ip', sa.String(), nullable=True))

    # 2. Add device tracking and activity columns to user_sessions table
    op.add_column('user_sessions', sa.Column('device_name', sa.String(), nullable=True))
    op.add_column('user_sessions', sa.Column('device_type', sa.String(), nullable=True))
    op.add_column('user_sessions', sa.Column('last_active_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True))
    op.add_column('user_sessions', sa.Column('last_ip', sa.String(), nullable=True))

    # 3. Create password_history table
    op.create_table(
        'password_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_password_history_id', 'password_history', ['id'], unique=False)
    op.create_index('ix_password_history_user_id', 'password_history', ['user_id'], unique=False)
    op.create_index('ix_password_history_user_created', 'password_history', ['user_id', 'created_at'], unique=False)

    # 4. Create used_refresh_tokens table for token rotation & reuse detection
    op.create_table(
        'used_refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_used_refresh_tokens_id', 'used_refresh_tokens', ['id'], unique=False)
    op.create_index('ix_used_refresh_tokens_user_id', 'used_refresh_tokens', ['user_id'], unique=False)
    op.create_index('ix_used_refresh_tokens_token_hash', 'used_refresh_tokens', ['token_hash'], unique=True)

    # 5. Create security_events table
    op.create_table(
        'security_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), server_default='info', nullable=False),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('device_info', sa.String(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_security_events_id', 'security_events', ['id'], unique=False)
    op.create_index('ix_security_events_user_id', 'security_events', ['user_id'], unique=False)
    op.create_index('ix_security_events_event_type', 'security_events', ['event_type'], unique=False)
    op.create_index('ix_security_events_ip_address', 'security_events', ['ip_address'], unique=False)
    op.create_index('ix_security_events_created_at', 'security_events', ['created_at'], unique=False)

def downgrade() -> None:
    op.drop_table('security_events')
    op.drop_table('used_refresh_tokens')
    op.drop_table('password_history')
    op.drop_column('user_sessions', 'last_ip')
    op.drop_column('user_sessions', 'last_active_at')
    op.drop_column('user_sessions', 'device_type')
    op.drop_column('user_sessions', 'device_name')
    op.drop_column('users', 'last_login_ip')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
