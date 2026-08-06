import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from backend.cache import safe_json_dumps, UnifiedCache, custom_json_serializer
from backend.config import Settings
from backend.database.database import check_db_connection
from scripts.validate_migrations import validate_alembic_migrations

def test_alembic_migration_validation():
    """Verify that Alembic migrations pass validation cleanly with single linear head."""
    result = validate_alembic_migrations()
    assert result is True

def test_cache_safe_json_serialization():
    """Verify custom JSON serialization handles datetime, Decimal, UUID, sets, and pydantic objects without error."""
    now = datetime.utcnow()
    uid = uuid4()
    dec = Decimal("19.99")
    data = {
        "timestamp": now,
        "uuid": uid,
        "price": dec,
        "tags": {"seo", "audit"},
        "nested": {"status": "ok"}
    }
    serialized = safe_json_dumps(data)
    assert isinstance(serialized, str)
    assert now.isoformat() in serialized
    assert str(uid) in serialized
    assert "19.99" in serialized

def test_production_config_validation():
    """Verify strict environment validation catches default development secrets in production mode."""
    insecure_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="super-secret-jwt-key-for-development-mode-12345",
        DATABASE_URL="postgresql://user:pass@localhost:5432/seodb"
    )
    with pytest.raises(ValueError) as exc_info:
        insecure_settings.validate_startup()
    assert "CRITICAL SECURITY ERROR" in str(exc_info.value)

    valid_prod_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a_very_secure_production_jwt_secret_key_with_at_least_32_characters_123456",
        DATABASE_URL="postgresql://user:pass@localhost:5432/seodb",
        REDIS_URL="redis://localhost:6379/0"
    )
    warnings = valid_prod_settings.validate_startup()
    assert isinstance(warnings, list)

@pytest.mark.asyncio
async def test_database_connection_check():
    """Verify async database connectivity check utility."""
    is_connected = await check_db_connection()
    assert is_connected is True
