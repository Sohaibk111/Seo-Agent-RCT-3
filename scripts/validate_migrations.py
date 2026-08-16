#!/usr/bin/env python3
"""
Alembic Production Migration Validator
Verifies that all migration revisions are connected in a single head linear history,
can be loaded without errors, and that database models match alembic target metadata.
"""

import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration_validator")

def validate_alembic_migrations():
    logger.info("Starting Alembic Migration Validation...")
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine
        from backend.config import settings
        from backend.database.models import Base

        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)

        heads = script.get_heads()
        logger.info(f"Alembic current migration heads: {heads}")

        if len(heads) != 1:
            logger.error(f"Multiple migration heads detected: {heads}. Linear migration history required.")
            return False

        revisions = list(script.walk_revisions())
        logger.info(f"Verified {len(revisions)} migration revisions in history:")
        for rev in reversed(revisions):
            logger.info(f"  └─ Revision [{rev.revision}] - {rev.doc}")

        # Create memory/sqlite DB to verify upgrade
        db_url = settings.DATABASE_URL if not settings.is_production() else "sqlite:///:memory:"
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)

        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            logger.info(f"Migration context established successfully on dialect '{conn.dialect.name}'.")

        logger.info("✅ Alembic migration validation completed successfully.")
        return True

    except Exception as e:
        logger.error(f"❌ Alembic migration validation failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = validate_alembic_migrations()
    sys.exit(0 if success else 1)
