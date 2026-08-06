from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime
from urllib.parse import urlparse
import re

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
    password: Optional[str] = Field(None, min_length=6, max_length=128)

class UserOut(UserBase):
    id: int
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None

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
