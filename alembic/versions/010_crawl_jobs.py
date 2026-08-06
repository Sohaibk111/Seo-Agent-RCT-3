"""crawl jobs, pages, and issues infrastructure

Revision ID: 010_crawl_jobs
Revises: 009_website_management
Create Date: 2026-08-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '010_crawl_jobs'
down_revision = '009_website_management'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create crawl_jobs table
    op.create_table(
        'crawl_jobs',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('website_id', sa.Integer(), sa.ForeignKey('websites.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(), server_default='queued', nullable=False),
        sa.Column('progress', sa.Integer(), server_default='0', nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('pages_found', sa.Integer(), server_default='0', nullable=False),
        sa.Column('issues_found', sa.Integer(), server_default='0', nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('triggered_by', sa.String(), server_default='manual', nullable=False),
        sa.Column('crawler_version', sa.String(), server_default='1.0.0', nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_crawl_jobs_id', 'crawl_jobs', ['id'], unique=False)
    op.create_index('ix_crawl_jobs_website_id', 'crawl_jobs', ['website_id'], unique=False)
    op.create_index('ix_crawl_jobs_status', 'crawl_jobs', ['status'], unique=False)
    op.create_index('ix_crawl_jobs_website_status', 'crawl_jobs', ['website_id', 'status'], unique=False)

    # Create crawl_pages table
    op.create_table(
        'crawl_pages',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('crawl_job_id', sa.Integer(), sa.ForeignKey('crawl_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('depth', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('content_type', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('meta_description', sa.Text(), nullable=True),
        sa.Column('canonical', sa.String(), nullable=True),
        sa.Column('h1', sa.String(), nullable=True),
        sa.Column('word_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('internal_links', sa.Integer(), server_default='0', nullable=False),
        sa.Column('external_links', sa.Integer(), server_default='0', nullable=False),
        sa.Column('noindex', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('nofollow', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('redirect_target', sa.String(), nullable=True),
        sa.Column('response_time', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_crawl_pages_id', 'crawl_pages', ['id'], unique=False)
    op.create_index('ix_crawl_pages_crawl_job_id', 'crawl_pages', ['crawl_job_id'], unique=False)
    op.create_index('ix_crawl_pages_url', 'crawl_pages', ['url'], unique=False)

    # Create crawl_issues table
    op.create_table(
        'crawl_issues',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('crawl_job_id', sa.Integer(), sa.ForeignKey('crawl_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('page_id', sa.Integer(), sa.ForeignKey('crawl_pages.id', ondelete='CASCADE'), nullable=True),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_crawl_issues_id', 'crawl_issues', ['id'], unique=False)
    op.create_index('ix_crawl_issues_crawl_job_id', 'crawl_issues', ['crawl_job_id'], unique=False)
    op.create_index('ix_crawl_issues_page_id', 'crawl_issues', ['page_id'], unique=False)
    op.create_index('ix_crawl_issues_severity', 'crawl_issues', ['severity'], unique=False)

def downgrade() -> None:
    op.drop_table('crawl_issues')
    op.drop_table('crawl_pages')
    op.drop_table('crawl_jobs')
