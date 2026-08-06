from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import relationship
from backend.database.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    role = Column(String, default="user")
    is_verified = Column(Boolean, default=False, nullable=False)
    avatar_url = Column(String, nullable=True)
    timezone = Column(String, default="UTC", nullable=False)
    language = Column(String, default="en", nullable=False)
    notification_settings = Column(JSON, default=dict)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    websites = relationship("Website", back_populates="owner", cascade="all, delete-orphan")
    audits = relationship("AuditResult", back_populates="owner", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="owner", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="owner", cascade="all, delete-orphan")
    keywords = relationship("KeywordResult", back_populates="owner", cascade="all, delete-orphan")
    rank_checks = relationship("RankCheck", back_populates="owner", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="owner", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    email_verification_tokens = relationship("EmailVerificationToken", back_populates="user", cascade="all, delete-orphan")
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")
    password_history = relationship("PasswordHistory", back_populates="user", cascade="all, delete-orphan")
    security_events = relationship("SecurityEvent", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")


class Website(Base):
    __tablename__ = "websites"
    __table_args__ = (
        Index("ix_websites_user_domain", "user_id", "domain"),
        Index("ix_websites_user_created", "user_id", "created_at"),
        Index("ix_websites_project_id", "project_id"),
        Index("ix_websites_organization_id", "organization_id"),
        Index("ix_websites_owner_id", "owner_id"),
        Index("ix_websites_domain", "domain"),
        Index("ix_websites_normalized_domain", "normalized_domain"),
        Index("ix_websites_org_normalized_domain", "organization_id", "normalized_domain", unique=True),
        Index("ix_websites_project_archived", "project_id", "archived"),
        Index("ix_websites_org_archived", "organization_id", "archived"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    url = Column(String, nullable=True)
    domain = Column(String, index=True, nullable=False)
    normalized_domain = Column(String, index=True, nullable=False)
    protocol = Column(String, default="https", nullable=False)
    status = Column(String, default="active", nullable=False)
    verification_status = Column(String, default="unverified", nullable=False)
    favicon = Column(String, nullable=True)
    country = Column(String, nullable=True)
    language = Column(String, default="en", nullable=False)
    timezone = Column(String, default="UTC", nullable=False)
    settings = Column(JSON, default=dict)
    company_name = Column(String, nullable=True)
    last_scan_at = Column(DateTime, nullable=True)
    archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="websites")
    organization = relationship("Organization", back_populates="websites")
    owner = relationship("User", back_populates="websites")
    audits = relationship("AuditResult", back_populates="website", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="website", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="website", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="website", cascade="all, delete-orphan")
    crawl_jobs = relationship("CrawlJob", back_populates="website", cascade="all, delete-orphan")


class AuditResult(Base):
    __tablename__ = "audit_results"
    __table_args__ = (
        Index("ix_audit_results_user_website", "user_id", "website_id"),
        Index("ix_audit_results_website_user_created", "website_id", "user_id", "created_at"),
        Index("ix_audit_results_website_user_score", "website_id", "user_id", "score"),
    )

    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Integer, nullable=False, default=100)
    title = Column(String, nullable=True)
    title_length = Column(Integer, nullable=True)
    meta_description = Column(Text, nullable=True)
    meta_description_length = Column(Integer, nullable=True)
    h1_tags = Column(JSON, default=list)
    canonical_url = Column(String, nullable=True)
    viewport = Column(String, nullable=True)
    images_count = Column(Integer, default=0)
    images_without_alt = Column(Integer, default=0)
    has_structured_data = Column(Boolean, default=False)
    has_sitemap = Column(Boolean, default=False)
    has_robots_txt = Column(Boolean, default=False)
    broken_links_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    website = relationship("Website", back_populates="audits")
    owner = relationship("User", back_populates="audits")


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_user_website", "user_id", "website_id"),
        Index("ix_leads_website_user_source", "website_id", "user_id", "source"),
        Index("ix_leads_website_user_created", "website_id", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    source = Column(String, default="audit")
    created_at = Column(DateTime, default=datetime.utcnow)

    website = relationship("Website", back_populates="leads")
    owner = relationship("User", back_populates="leads")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_user_website", "user_id", "website_id"),
        Index("ix_reports_website_user_format", "website_id", "user_id", "format"),
        Index("ix_reports_website_user_created", "website_id", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    format = Column(String, default="pdf")
    created_at = Column(DateTime, default=datetime.utcnow)

    website = relationship("Website", back_populates="reports")
    owner = relationship("User", back_populates="reports")


class KeywordResult(Base):
    __tablename__ = "keyword_results"
    __table_args__ = (
        Index("ix_keyword_results_user_seed", "user_id", "seed_keyword"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    seed_keyword = Column(String, nullable=False, index=True)
    keyword = Column(String, nullable=False)
    intent = Column(String, default="Informational")
    volume = Column(Integer, default=0)
    kd = Column(Integer, default=0)
    cpc = Column(Text, default="0.00")
    cluster = Column(String, default="General")
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="keywords")


class RankCheck(Base):
    __tablename__ = "rank_checks"
    __table_args__ = (
        Index("ix_rank_checks_user_domain", "user_id", "domain"),
        Index("ix_rank_checks_user_website", "user_id", "website_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    keyword = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    position = Column(Integer, nullable=False)
    checked_results = Column(Integer, default=30)
    source = Column(String, default="free_tracker")
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="rank_checks")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_user_status", "user_id", "status"),
        Index("ix_jobs_user_type", "user_id", "job_type"),
        Index("ix_jobs_user_created", "user_id", "created_at"),
        Index("ix_jobs_status_updated", "status", "updated_at"),
        Index("ix_jobs_user_updated", "user_id", "updated_at"),
        Index("ix_jobs_user_website", "user_id", "website_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    website_id = Column(Integer, ForeignKey("websites.id", ondelete="CASCADE"), nullable=True, index=True)
    job_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="pending", index=True)
    progress = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(Text, nullable=True)
    result_reference = Column(JSON, nullable=True)

    owner = relationship("User", back_populates="jobs")
    website = relationship("Website", back_populates="jobs")


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("ix_user_sessions_user_active", "user_id", "is_active"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token = Column(String, unique=True, index=True, nullable=False)
    refresh_token = Column(String, unique=True, index=True, nullable=False)
    ip_address = Column(String, nullable=True)
    last_ip = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    device_name = Column(String, nullable=True)
    device_type = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    remember_me = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_active_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="sessions")


class PasswordHistory(Base):
    __tablename__ = "password_history"
    __table_args__ = (
        Index("ix_password_history_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="password_history")


class UsedRefreshToken(Base):
    __tablename__ = "used_refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, nullable=True, index=True)
    token_hash = Column(String, unique=True, index=True, nullable=False)
    revoked_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    status = Column(String, default="info", nullable=False)
    ip_address = Column(String, nullable=True, index=True)
    user_agent = Column(String, nullable=True)
    device_info = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="security_events")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="password_reset_tokens")


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="email_verification_tokens")


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    logo_url = Column(String, nullable=True)
    primary_color = Column(String, nullable=True)
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memberships = relationship("Membership", back_populates="organization", cascade="all, delete-orphan")
    invitations = relationship("Invitation", back_populates="organization", cascade="all, delete-orphan")
    audit_events = relationship("OrganizationAuditEvent", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")
    websites = relationship("Website", back_populates="organization", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        Index("ix_memberships_org_user", "organization_id", "user_id", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, default="Member", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="memberships")
    user = relationship("User", back_populates="memberships")


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String, index=True, nullable=False)
    role = Column(String, default="Member", nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="pending", nullable=False)
    invited_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="invitations")
    invited_by = relationship("User")


class OrganizationAuditEvent(Base):
    __tablename__ = "organization_audit_events"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="audit_events")
    actor = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    target_resource = Column(String, nullable=True, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")
    organization = relationship("Organization")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_org_slug", "organization_id", "slug", unique=True),
        Index("ix_projects_org_archived", "organization_id", "archived"),
        Index("ix_projects_org_status", "organization_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="active", nullable=False)
    color = Column(String, nullable=True)
    icon = Column(String, nullable=True)
    timezone = Column(String, default="UTC", nullable=False)
    language = Column(String, default="en", nullable=False)
    settings = Column(JSON, default=dict)
    archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="projects")
    owner = relationship("User", back_populates="projects")
    websites = relationship("Website", back_populates="project", cascade="all, delete-orphan")


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    __table_args__ = (
        Index("ix_crawl_jobs_website_id", "website_id"),
        Index("ix_crawl_jobs_status", "status"),
        Index("ix_crawl_jobs_website_status", "website_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, default="queued", nullable=False, index=True)
    progress = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    pages_found = Column(Integer, default=0, nullable=False)
    issues_found = Column(Integer, default=0, nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    triggered_by = Column(String, default="manual", nullable=False)
    crawler_version = Column(String, default="1.0.0", nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    website = relationship("Website", back_populates="crawl_jobs")
    pages = relationship("CrawlPage", back_populates="crawl_job", cascade="all, delete-orphan")
    issues = relationship("CrawlIssue", back_populates="crawl_job", cascade="all, delete-orphan")


class CrawlPage(Base):
    __tablename__ = "crawl_pages"
    __table_args__ = (
        Index("ix_crawl_pages_crawl_job_id", "crawl_job_id"),
        Index("ix_crawl_pages_url", "url"),
    )

    id = Column(Integer, primary_key=True, index=True)
    crawl_job_id = Column(Integer, ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(String, nullable=False, index=True)
    depth = Column(Integer, default=0, nullable=False)
    status_code = Column(Integer, nullable=True)
    content_type = Column(String, nullable=True)
    title = Column(String, nullable=True)
    meta_description = Column(Text, nullable=True)
    canonical = Column(String, nullable=True)
    h1 = Column(String, nullable=True)
    word_count = Column(Integer, default=0, nullable=False)
    internal_links = Column(Integer, default=0, nullable=False)
    external_links = Column(Integer, default=0, nullable=False)
    noindex = Column(Boolean, default=False, nullable=False)
    nofollow = Column(Boolean, default=False, nullable=False)
    redirect_target = Column(String, nullable=True)
    response_time = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    crawl_job = relationship("CrawlJob", back_populates="pages")
    issues = relationship("CrawlIssue", back_populates="page", cascade="all, delete-orphan")


class CrawlIssue(Base):
    __tablename__ = "crawl_issues"
    __table_args__ = (
        Index("ix_crawl_issues_crawl_job_id", "crawl_job_id"),
        Index("ix_crawl_issues_page_id", "page_id"),
        Index("ix_crawl_issues_severity", "severity"),
    )

    id = Column(Integer, primary_key=True, index=True)
    crawl_job_id = Column(Integer, ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    page_id = Column(Integer, ForeignKey("crawl_pages.id", ondelete="CASCADE"), nullable=True, index=True)
    severity = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    crawl_job = relationship("CrawlJob", back_populates="issues")
    page = relationship("CrawlPage", back_populates="issues")




