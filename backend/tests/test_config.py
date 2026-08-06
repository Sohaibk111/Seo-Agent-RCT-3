import pytest
import os
from pydantic import ValidationError
from backend.config import Settings

def test_default_config_validation():
    s = Settings()
    assert s.PROJECT_NAME == "SEO Agent API"
    assert s.ENVIRONMENT == "development"
    assert s.ALGORITHM == "HS256"
    assert s.is_production() is False

def test_invalid_environment_value():
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="invalid_env_name")

def test_short_secret_key():
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="short")

def test_production_mode_checks():
    # Default secret key in production should raise error during startup validation
    prod_s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="super-secret-jwt-key-for-development-mode-12345"
    )
    with pytest.raises(ValueError, match="Default development SECRET_KEY used in production"):
        prod_s.validate_startup()

    # Valid secret key in production should pass
    valid_prod_s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a-secure-production-jwt-secret-key-that-is-very-long"
    )
    warnings = valid_prod_s.validate_startup()
    assert isinstance(warnings, list)
