# Backend exception definitions
from typing import Optional, Dict, Any

class SEOAgentException(Exception):
    """Base exception for SEO Agent application."""
    def __init__(self, message: str, status_code: int = 400, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class UnauthorizedException(SEOAgentException):
    def __init__(self, message: str = "Authentication credentials were missing or invalid", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=401, details=details)

class ForbiddenException(SEOAgentException):
    def __init__(self, message: str = "Forbidden: You do not have permission to access this resource", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=403, details=details)

class ResourceNotFoundException(SEOAgentException):
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=404, details=details)

class ConflictException(SEOAgentException):
    def __init__(self, message: str = "Resource conflict or already exists", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=409, details=details)

class ValidationErrorException(SEOAgentException):
    def __init__(self, message: str = "Request validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=422, details=details)

class RateLimitException(SEOAgentException):
    def __init__(self, message: str = "Too many requests, rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=429, details=details)

class InternalServerException(SEOAgentException):
    def __init__(self, message: str = "An internal server error occurred", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=500, details=details)

