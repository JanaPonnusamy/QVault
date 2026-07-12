"""Idempotent SQL Server database/schema bootstrap, run at startup.

Only exercised when the resolved engine dialect is "mssql" (see
database/session.py::init_db). SQLite (the local dev default) has no
multi-database/multi-schema concept, so this module is a no-op there.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from app.config.settings import settings
from app.shared.logging import get_logger

logger = get_logger("mssql_bootstrap")

# Schemas reserved for the platform's modules. Only `catalog` (and `system`,
# for import logging) have tables today; the rest are created empty so future
# modules (question bank, knowledge graph, media, video registry, acquisition)
# can adopt them without another startup change.
RESERVED_SCHEMAS = ["catalog", "question", "knowledge", "media", "video", "acquisition", "system"]


def ensure_database() -> None:
    """Create settings.mssql_database if IF DB_ID(...) shows it doesn't exist yet."""
    import pyodbc

    conn = pyodbc.connect(settings.mssql_master_odbc_connect, autocommit=True)
    try:
        cur = conn.cursor()
        exists = cur.execute("SELECT DB_ID(?)", settings.mssql_database).fetchone()[0] is not None
        if exists:
            logger.info("SQL Server database '%s' already exists.", settings.mssql_database)
            return
        cur.execute(f"CREATE DATABASE [{settings.mssql_database}]")
        logger.info("Created SQL Server database '%s'.", settings.mssql_database)
    finally:
        conn.close()


def ensure_schemas(engine: Engine) -> None:
    """Create any of RESERVED_SCHEMAS that don't already exist (IF SCHEMA_ID(...) IS NULL)."""
    with engine.begin() as conn:
        for schema in RESERVED_SCHEMAS:
            conn.exec_driver_sql(
                f"IF SCHEMA_ID(N'{schema}') IS NULL EXEC('CREATE SCHEMA {schema}')"
            )
    logger.info("Verified SQL Server schemas: %s", ", ".join(RESERVED_SCHEMAS))


def bootstrap(engine: Engine) -> None:
    """Reconnect-and-create sequence: ensure the database exists, then its schemas.

    Must run before Base.metadata.create_all() so schema-qualified tables
    (catalog.*, system.*) have somewhere to be created into.
    """
    ensure_database()
    ensure_schemas(engine)
