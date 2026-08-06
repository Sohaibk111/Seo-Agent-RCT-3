from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime
from urllib.parse import urlparse
import re
from enum import Enum

# Helper functions for validation
def validate_url_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    if not v:
        raise ValueError("URL cannot be empty")
    if not (v.startswith("http://") or v.startswith("https://")):
        v = "https://" + v
    parsed = urlparse(v)
    if not parsed.netloc:
        raise ValueError("Invalid URL format")
    return v

def validate_domain_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip().lower()
    if not v:
        return None
    if v.startswith("http://") or v.startswith("https://"):
        v = urlparse(v).netloc or v
    v = v.split("/")[0].split(":")[0]
    if not re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
        raise ValueError("Invalid domain name format")
    return v

def validate_keyword_str(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Keyword cannot be empty")
    return v.strip()

def validate_password_strength_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not any(c.isupper() for c in v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one numeric digit")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", v):
        raise ValueError("Password must contain at least one special character")
    common_passwords = {"password", "12345678", "123456789", "admin123", "qwerty123", "letmein1", "welcome1", "iloveyou"}
    if v.lower() in common_passwords:
        raise ValueError("Password is too common or easily guessable")
    return v

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=2, max_length=50)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username cannot be empty or blank")
        return v

class UserCreate(UserBase):
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    remember_me: Optional[bool] = False

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        return validate_password_strength_str(v)

class UserLogin(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = Field(None, min_length=1, max_length=128)


class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Friendly name for the API key")


class APIKeyOut(BaseModel):
    id: str
    name: str
    api_key: str
    created_at: datetime

    remember_me: Optional[bool] = False

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=2, max_length=50)
    email: Optional[EmailStr] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    notification_settings: Optional[dict] = None
    avatar_url: Optional[str] = None

class UserOut(UserBase):
    id: int
    role: str
    is_verified: bool = False
    avatar_url: Optional[str] = None
    timezone: str = "UTC"
    language: str = "en"
    notification_settings: Optional[dict] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# SaaS Auth Schemas
class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user_id: Optional[int] = None
    username: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        res = validate_password_strength_str(v)
        return res or v

class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_change_password(cls, v: str) -> str:
        res = validate_password_strength_str(v)
        return res or v

class EmailVerificationRequest(BaseModel):
    email: Optional[EmailStr] = None

class EmailVerificationConfirm(BaseModel):
    token: str

class AvatarUpdate(BaseModel):
    avatar_url: str

class SessionOut(BaseModel):
    id: int
    user_id: int
    ip_address: Optional[str] = None
    last_ip: Optional[str] = None
    user_agent: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    is_active: bool
    remember_me: bool
    last_active_at: Optional[datetime] = None
    created_at: datetime
    expires_at: datetime
    is_current: Optional[bool] = False

    class Config:
        from_attributes = True

class SecurityEventOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    event_type: str
    status: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_info: Optional[str] = None
    details: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True

class CSRFTokenOut(BaseModel):
    csrf_token: str
    header_name: str = "X-CSRF-Token"

class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None


# Organization & Team Schemas
class OrganizationRole(str, Enum):
    OWNER = "Owner"
    ADMIN = "Admin"
    MANAGER = "Manager"
    MEMBER = "Member"
    VIEWER = "Viewer"


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    settings: Optional[dict] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    settings: Optional[dict] = None


class OrganizationOut(BaseModel):
    id: int
    name: str
    slug: str
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    settings: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MembershipOut(BaseModel):
    id: int
    organization_id: int
    user_id: int
    role: str
    created_at: datetime
    updated_at: datetime
    user: Optional[UserOut] = None

    class Config:
        from_attributes = True


class MemberRoleUpdate(BaseModel):
    role: str = Field(..., description="Role must be one of: Owner, Admin, Manager, Member, Viewer")


class OwnershipTransfer(BaseModel):
    new_owner_user_id: int


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field("Member", description="Role: Owner, Admin, Manager, Member, Viewer")


class InvitationOut(BaseModel):
    id: int
    organization_id: int
    email: str
    role: str
    status: str
    token: str
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class InvitationConfirm(BaseModel):
    token: str


class OrganizationAuditEventOut(BaseModel):
    id: int
    organization_id: int
    actor_id: Optional[int] = None
    action: str
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    organization_id: Optional[int] = None
    action: str
    target_resource: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogPaginated(BaseModel):
    items: List[AuditLogOut]
    total: int
    page: int
    size: int
    total_pages: int



# Website Schemas
class WebsiteBase(BaseModel):
    url: str
    domain: Optional[str] = None
    company_name: Optional[str] = Field(None, max_length=100)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        res = validate_url_str(v)
        if not res:
            raise ValueError("URL is required")
        return res

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: Optional[str]) -> Optional[str]:
        return validate_domain_str(v)

class WebsiteCreate(WebsiteBase):
    pass

class WebsiteOut(WebsiteBase):
    id: int
    user_id: int
    domain: str
    created_at: datetime

    class Config:
        from_attributes = True

# Audit Schemas
class AuditCreate(BaseModel):
    url: Optional[str] = None
    website_id: Optional[int] = Field(None, ge=1)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_url_str(v)

class AuditOut(BaseModel):
    id: int
    website_id: int
    user_id: int
    score: int
    title: Optional[str] = None
    title_length: Optional[int] = None
    meta_description: Optional[str] = None
    meta_description_length: Optional[int] = None
    h1_tags: List[str] = []
    canonical_url: Optional[str] = None
    viewport: Optional[str] = None
    images_count: int
    images_without_alt: int
    has_structured_data: bool
    has_sitemap: bool
    has_robots_txt: bool
    broken_links_count: int
    created_at: datetime

    class Config:
        from_attributes = True

# Lead Schemas
class LeadOut(BaseModel):
    id: int
    website_id: Optional[int] = None
    user_id: int
    email: str
    phone: Optional[str] = None
    source: str
    created_at: datetime

    class Config:
        from_attributes = True

# Report Schemas
class ReportOut(BaseModel):
    id: int
    website_id: int
    user_id: int
    title: str
    format: str
    created_at: datetime

    class Config:
        from_attributes = True

class ReportExportRequest(BaseModel):
    website_id: int = Field(..., ge=1)
    format: Optional[str] = Field("pdf", pattern="^(pdf|csv|json|html)$")

# Keyword Schemas
class KeywordRequest(BaseModel):
    seed_keyword: str = Field(..., min_length=1, max_length=100)
    limit: Optional[int] = Field(10, ge=1, le=100)

    @field_validator("seed_keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        return validate_keyword_str(v)

class KeywordOut(BaseModel):
    kw: str
    intent: str
    volume: int
    kd: int
    cpc: float
    cluster: str

# Rank Tracker Schemas
class RankCheckRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=150)
    domain: Optional[str] = Field(None, max_length=255)
    website_id: Optional[int] = Field(None, ge=1)

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        return validate_keyword_str(v)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: Optional[str]) -> Optional[str]:
        return validate_domain_str(v)

class RankCheckOut(BaseModel):
    keyword: str
    domain: str
    position: int
    checked_results: int
    source: str

# Domain Metrics Schemas
class DomainMetricsRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=255)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        res = validate_domain_str(v)
        if not res:
            raise ValueError("Domain is required and must be valid")
        return res

class DomainMetricsOut(BaseModel):
    domain: str
    provider: str
    domain_age_days: int
    registrar: str
    domain_authority: int
    backlinks_estimate: int
    organic_traffic_monthly: int

# Job Schemas
class JobOut(BaseModel):
    id: int
    user_id: int
    website_id: Optional[int] = None
    job_type: str
    status: str
    progress: int
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    updated_at: datetime
    error_message: Optional[str] = None
    result_reference: Optional[Any] = None

    class Config:
        from_attributes = True

class CrawlJobRequest(BaseModel):
    url: Optional[str] = None
    website_id: Optional[int] = Field(None, ge=1)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_url_str(v)

class AuditJobRequest(BaseModel):
    url: Optional[str] = None
    website_id: Optional[int] = Field(None, ge=1)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_url_str(v)

class KeywordJobRequest(BaseModel):
    seed_keyword: str = Field(..., min_length=1, max_length=100)
    limit: Optional[int] = Field(10, ge=1, le=100)

    @field_validator("seed_keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        return validate_keyword_str(v)

class RankJobRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=150)
    domain: Optional[str] = Field(None, max_length=255)
    website_id: Optional[int] = Field(None, ge=1)

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        return validate_keyword_str(v)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: Optional[str]) -> Optional[str]:
        return validate_domain_str(v)
