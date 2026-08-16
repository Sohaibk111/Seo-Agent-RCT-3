"""add composite indexes for performance

Revision ID: 002_add_composite_indexes
Revises: 001_create_jobs_table
Create Date: 2026-08-02 10:42:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_add_composite_indexes'
down_revision = '001_create_jobs_table'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_index('ix_websites_user_domain', 'websites', ['user_id', 'domain'], unique=False)
    op.create_index('ix_audit_results_user_website', 'audit_results', ['user_id', 'website_id'], unique=False)
    op.create_index('ix_leads_user_website', 'leads', ['user_id', 'website_id'], unique=False)
    op.create_index('ix_reports_user_website', 'reports', ['user_id', 'website_id'], unique=False)
    op.create_index('ix_keyword_results_user_seed', 'keyword_results', ['user_id', 'seed_keyword'], unique=False)
    op.create_index('ix_rank_checks_user_domain', 'rank_checks', ['user_id', 'domain'], unique=False)
    op.create_index('ix_rank_checks_user_website', 'rank_checks', ['user_id', 'website_id'], unique=False)
    op.create_index('ix_jobs_user_status', 'jobs', ['user_id', 'status'], unique=False)
    op.create_index('ix_jobs_user_type', 'jobs', ['user_id', 'job_type'], unique=False)
    op.create_index('ix_jobs_user_created', 'jobs', ['user_id', 'created_at'], unique=False)

def downgrade() -> None:
    op.drop_index('ix_jobs_user_created', table_name='jobs')
    op.drop_index('ix_jobs_user_type', table_name='jobs')
    op.drop_index('ix_jobs_user_status', table_name='jobs')
    op.drop_index('ix_rank_checks_user_website', table_name='rank_checks')
    op.drop_index('ix_rank_checks_user_domain', table_name='rank_checks')
    op.drop_index('ix_keyword_results_user_seed', table_name='keyword_results')
    op.drop_index('ix_reports_user_website', table_name='reports')
    op.drop_index('ix_leads_user_website', table_name='leads')
    op.drop_index('ix_audit_results_user_website', table_name='audit_results')
    op.drop_index('ix_websites_user_domain', table_name='websites')
