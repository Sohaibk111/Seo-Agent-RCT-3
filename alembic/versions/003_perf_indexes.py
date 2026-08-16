"""add database performance indexes

Revision ID: 003_perf_indexes
Revises: 002_add_composite_indexes
Create Date: 2026-08-04 08:24:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_perf_indexes'
down_revision = '002_add_composite_indexes'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_index('ix_websites_user_created', 'websites', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_audit_results_website_user_created', 'audit_results', ['website_id', 'user_id', 'created_at'], unique=False)
    op.create_index('ix_audit_results_website_user_score', 'audit_results', ['website_id', 'user_id', 'score'], unique=False)
    op.create_index('ix_leads_website_user_source', 'leads', ['website_id', 'user_id', 'source'], unique=False)
    op.create_index('ix_leads_website_user_created', 'leads', ['website_id', 'user_id', 'created_at'], unique=False)
    op.create_index('ix_reports_website_user_format', 'reports', ['website_id', 'user_id', 'format'], unique=False)
    op.create_index('ix_reports_website_user_created', 'reports', ['website_id', 'user_id', 'created_at'], unique=False)
    op.create_index('ix_jobs_status_updated', 'jobs', ['status', 'updated_at'], unique=False)
    op.create_index('ix_jobs_user_updated', 'jobs', ['user_id', 'updated_at'], unique=False)
    op.create_index('ix_jobs_user_website', 'jobs', ['user_id', 'website_id'], unique=False)

def downgrade() -> None:
    op.drop_index('ix_jobs_user_website', table_name='jobs')
    op.drop_index('ix_jobs_user_updated', table_name='jobs')
    op.drop_index('ix_jobs_status_updated', table_name='jobs')
    op.drop_index('ix_reports_website_user_created', table_name='reports')
    op.drop_index('ix_reports_website_user_format', table_name='reports')
    op.drop_index('ix_leads_website_user_created', table_name='leads')
    op.drop_index('ix_leads_website_user_source', table_name='leads')
    op.drop_index('ix_audit_results_website_user_score', table_name='audit_results')
    op.drop_index('ix_audit_results_website_user_created', table_name='audit_results')
    op.drop_index('ix_websites_user_created', table_name='websites')
