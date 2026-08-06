from functools import lru_cache
import os
import logging
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("seo_agent.config")

class Settings(BaseModel):
    PROJECT_NAME: str = "SEO Agent API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development").lower())
    
    SECRET_KEY: str = Field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", "super-secret-jwt-key-for-development-mode-12345"))
    ALGORITHM: str = Field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default_factory=lambda: int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")))
    
    DATABASE_URL: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./seo_agent.db"))
    DB_POOL_SIZE: int = Field(default_factory=lambda: int(os.getenv("DB_POOL_SIZE", "10")))
    DB_MAX_OVERFLOW: int = Field(default_factory=lambda: int(os.getenv("DB_MAX_OVERFLOW", "20")))
    DB_POOL_TIMEOUT: int = Field(default_factory=lambda: int(os.getenv("DB_POOL_TIMEOUT", "30")))
    DB_POOL_RECYCLE: int = Field(default_factory=lambda: int(os.getenv("DB_POOL_RECYCLE", "1800")))
    GEMINI_API_KEY: Optional[str] = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", None))
    
    # Redis & Queue Settings
    REDIS_URL: Optional[str] = Field(default_factory=lambda: os.getenv("REDIS_URL", None))
    USE_REDIS_QUEUE: bool = Field(default_factory=lambda: os.getenv("USE_REDIS_QUEUE", "false").lower() in ("true", "1", "yes"))
    REDIS_MAX_CONNECTIONS: int = Field(default_factory=lambda: int(os.getenv("REDIS_MAX_CONNECTIONS", "50")))
    REDIS_SOCKET_TIMEOUT: float = Field(default_factory=lambda: float(os.getenv("REDIS_SOCKET_TIMEOUT", "2.0")))
    REDIS_CONNECT_TIMEOUT: float = Field(default_factory=lambda: float(os.getenv("REDIS_CONNECT_TIMEOUT", "1.0")))

    # Rate Limiting Settings
    RATE_LIMIT_ENABLED: bool = Field(default_factory=lambda: os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes"))
    RATE_LIMIT_PER_MINUTE: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")))

    # Sentry & Monitoring Settings
    SENTRY_DSN: Optional[str] = Field(default_factory=lambda: os.getenv("SENTRY_DSN", None))
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default_factory=lambda: float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0")))
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = Field(default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", None))
    OTEL_SERVICE_NAME: str = Field(default_factory=lambda: os.getenv("OTEL_SERVICE_NAME", "seo-agent-service"))
    OTEL_ENABLED: bool = Field(default_factory=lambda: os.getenv("OTEL_ENABLED", "true").lower() in ("true", "1", "yes"))

    # Worker & Execution Limits
    MAX_WORKERS: int = Field(default_factory=lambda: int(os.getenv("MAX_WORKERS", "4")))
    WORKER_CONCURRENCY: int = Field(default_factory=lambda: int(os.getenv("WORKER_CONCURRENCY", "4")))
    JOB_TIMEOUT_SECONDS: int = Field(default_factory=lambda: int(os.getenv("JOB_TIMEOUT_SECONDS", "300")))
    JOB_MAX_RETRIES: int = Field(default_factory=lambda: int(os.getenv("JOB_MAX_RETRIES", "2")))
    MAX_JOB_RETRIES: int = Field(default_factory=lambda: int(os.getenv("MAX_JOB_RETRIES", "3")))
    RETRY_BASE_DELAY: float = Field(default_factory=lambda: float(os.getenv("RETRY_BASE_DELAY", "1.0")))
    RETRY_MAX_DELAY: float = Field(default_factory=lambda: float(os.getenv("RETRY_MAX_DELAY", "60.0")))
    WORKER_HEARTBEAT_INTERVAL: int = Field(default_factory=lambda: int(os.getenv("WORKER_HEARTBEAT_INTERVAL", "10")))
    JOB_RECOVERY_ENABLED: bool = Field(default_factory=lambda: os.getenv("JOB_RECOVERY_ENABLED", "true").lower() in ("true", "1", "yes"))
    ENABLE_DEAD_LETTER_QUEUE: bool = Field(default_factory=lambda: os.getenv("ENABLE_DEAD_LETTER_QUEUE", "true").lower() in ("true", "1", "yes"))
    
    # Cache Configuration & TTL Values
    CACHE_TTL_DEFAULT: int = Field(default_factory=lambda: int(os.getenv("CACHE_TTL_DEFAULT", "300")))
    CACHE_TTL_METRICS: int = Field(default_factory=lambda: int(os.getenv("CACHE_TTL_METRICS", "1800")))
    CACHE_TTL_WHOIS: int = Field(default_factory=lambda: int(os.getenv("CACHE_TTL_WHOIS", "1800")))
    CACHE_TTL_SITEMAP: int = Field(default_factory=lambda: int(os.getenv("CACHE_TTL_SITEMAP", "600")))
    CACHE_TTL_ROBOTS: int = Field(default_factory=lambda: int(os.getenv("CACHE_TTL_ROBOTS", "600")))
    CACHE_TTL_KEYWORDS: int = Field(default_factory=lambda: int(os.getenv("CACHE_TTL_KEYWORDS", "600")))
    CACHE_TTL_AI: int = Field(default_factory=lambda: int(os.getenv("CACHE_TTL_AI", "1800")))
    CACHE_TTL_SERP: int = Field(default_factory=lambda: int(os.getenv("CACHE_TTL_SERP", "600")))
    CACHE_MAX_ITEMS: int = Field(default_factory=lambda: int(os.getenv("CACHE_MAX_ITEMS", "1000")))
    
    # Browser & Crawler Limits
    BROWSER_CONCURRENCY_LIMIT: int = Field(default_factory=lambda: int(os.getenv("BROWSER_CONCURRENCY_LIMIT", "5")))
    BROWSER_POOL_SIZE: int = Field(default_factory=lambda: int(os.getenv("BROWSER_POOL_SIZE", "5")))
    BROWSER_IDLE_TIMEOUT: float = Field(default_factory=lambda: float(os.getenv("BROWSER_IDLE_TIMEOUT", "60.0")))
    BROWSER_HEADLESS: bool = Field(default_factory=lambda: os.getenv("BROWSER_HEADLESS", "true").lower() == "true")
    BROWSER_PAGE_TIMEOUT_MS: int = Field(default_factory=lambda: int(os.getenv("BROWSER_PAGE_TIMEOUT_MS", "30000")))
    
    # HTTP Client Pooling Settings
    HTTP_MAX_CONNECTIONS: int = Field(default_factory=lambda: int(os.getenv("HTTP_MAX_CONNECTIONS", "100")))
    HTTP_MAX_KEEPALIVE_CONNECTIONS: int = Field(default_factory=lambda: int(os.getenv("HTTP_MAX_KEEPALIVE_CONNECTIONS", "20")))
    HTTP_KEEPALIVE_EXPIRY: float = Field(default_factory=lambda: float(os.getenv("HTTP_KEEPALIVE_EXPIRY", "30.0")))
    HTTP_TIMEOUT_CONNECT: float = Field(default_factory=lambda: float(os.getenv("HTTP_TIMEOUT_CONNECT", "5.0")))
    HTTP_TIMEOUT_READ: float = Field(default_factory=lambda: float(os.getenv("HTTP_TIMEOUT_READ", "10.0")))
    HTTP_TIMEOUT_WRITE: float = Field(default_factory=lambda: float(os.getenv("HTTP_TIMEOUT_WRITE", "5.0")))
    HTTP_TIMEOUT_POOL: float = Field(default_factory=lambda: float(os.getenv("HTTP_TIMEOUT_POOL", "5.0")))
    HTTP_MAX_RETRIES: int = Field(default_factory=lambda: int(os.getenv("HTTP_MAX_RETRIES", "3")))
    
    # Export Settings
    EXPORT_STREAM_CHUNK_SIZE: int = Field(default_factory=lambda: int(os.getenv("EXPORT_STREAM_CHUNK_SIZE", "8192")))
    
    # Compression Settings
    COMPRESSION_ENABLED: bool = Field(default_factory=lambda: os.getenv("COMPRESSION_ENABLED", "true").lower() == "true")
    COMPRESSION_MINIMUM_SIZE: int = Field(default_factory=lambda: int(os.getenv("COMPRESSION_MINIMUM_SIZE", "500")))
    COMPRESSION_BROTLI_QUALITY: int = Field(default_factory=lambda: int(os.getenv("COMPRESSION_BROTLI_QUALITY", "4")))
    COMPRESSION_GZIP_LEVEL: int = Field(default_factory=lambda: int(os.getenv("COMPRESSION_GZIP_LEVEL", "6")))
    
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: [
        origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()
    ])

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_env(cls, v: str) -> str:
        valid_envs = {"development", "staging", "production", "testing"}
        v = v.lower().strip()
        if v not in valid_envs:
            raise ValueError(f"ENVIRONMENT must be one of {valid_envs}")
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or len(v.strip()) < 16:
            raise ValueError("SECRET_KEY must be at least 16 characters long")
        return v

    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def validate_startup(self) -> List[str]:
        warnings = []
        if self.is_production():
            if "super-secret" in self.SECRET_KEY or "development" in self.SECRET_KEY or "12345" in self.SECRET_KEY:
                raise ValueError("CRITICAL SECURITY ERROR: Insecure or default development SECRET_KEY used in production environment!")
            if len(self.SECRET_KEY) < 32:
                warnings.append("WARNING: Production SECRET_KEY should be at least 32 characters long.")
            if self.DATABASE_URL.startswith("sqlite"):
                warnings.append("WARNING: SQLite database configured for production environment. PostgreSQL is recommended.")
            if "*" in self.CORS_ORIGINS:
                warnings.append("WARNING: Wildcard CORS origins '*' enabled in production environment.")
            if not self.REDIS_URL:
                warnings.append("WARNING: REDIS_URL not configured in production environment. In-memory queue/cache fallback active.")
        
        if not self.GEMINI_API_KEY:
            warnings.append("NOTICE: GEMINI_API_KEY is not set. AI features will operate in fallback mode.")
            
        for w in warnings:
            logger.warning(w)
            
        return warnings

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

