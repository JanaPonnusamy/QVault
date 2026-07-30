from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.settings import settings

engine = create_engine(
    settings.sqlalchemy_url,
    connect_args={"check_same_thread": False} if settings.is_sqlite else {},
    pool_pre_ping=not settings.is_sqlite,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Additive columns added to tables that already existed on some already-deployed
# database (SQLite dev files, and any SQL Server target initialized before the
# column was added to the model). create_all() only creates *missing tables* --
# it never ALTERs a table that's already there -- so every column added to an
# existing table's model must also be listed here, or dialects that were
# bootstrapped before that column existed silently keep missing it forever
# (this bit SQL Server: extraction_jobs/frames/questions were originally
# created at Platform Phase 1 v0.6.0, and every column added since then via
# this dict was, before this fix, only ever applied on SQLite).
#
# Each entry is per-dialect DDL (types/existence-checks differ: SQLite has no
# native BOOLEAN and uses PRAGMA table_info; SQL Server needs BIT and
# INFORMATION_SCHEMA.COLUMNS).
_NEW_COLUMNS: dict[str, dict[str, dict[str, str]]] = {
    "extraction_jobs": {
        "source": {"sqlite": "VARCHAR(20) DEFAULT 'youtube'", "mssql": "VARCHAR(20) DEFAULT 'youtube'"},
        "caption": {"sqlite": "TEXT DEFAULT ''", "mssql": "NVARCHAR(MAX) DEFAULT ''"},
        "author": {"sqlite": "VARCHAR(200) DEFAULT ''", "mssql": "VARCHAR(200) DEFAULT ''"},
        "upload_date": {"sqlite": "VARCHAR(20) DEFAULT ''", "mssql": "VARCHAR(20) DEFAULT ''"},
        "thumbnail_url": {"sqlite": "VARCHAR(1000) DEFAULT ''", "mssql": "VARCHAR(1000) DEFAULT ''"},
        "source_meta": {"sqlite": "TEXT DEFAULT ''", "mssql": "NVARCHAR(MAX) DEFAULT ''"},
        "extraction_strategy": {"sqlite": "VARCHAR(30) DEFAULT 'hybrid'", "mssql": "VARCHAR(30) DEFAULT 'hybrid'"},
        "extraction_options": {"sqlite": "TEXT DEFAULT ''", "mssql": "NVARCHAR(MAX) DEFAULT ''"},
    },
    "frames": {
        "question_score": {"sqlite": "FLOAT DEFAULT 0", "mssql": "FLOAT DEFAULT 0"},
        "is_question": {"sqlite": "BOOLEAN DEFAULT 0", "mssql": "BIT DEFAULT 0"},
        "is_duplicate": {"sqlite": "BOOLEAN DEFAULT 0", "mssql": "BIT DEFAULT 0"},
        "phash": {"sqlite": "VARCHAR(64) DEFAULT ''", "mssql": "VARCHAR(64) DEFAULT ''"},
        "ocr_text": {"sqlite": "TEXT DEFAULT ''", "mssql": "NVARCHAR(MAX) DEFAULT ''"},
        "ocr_confidence": {"sqlite": "FLOAT DEFAULT 0", "mssql": "FLOAT DEFAULT 0"},
        "ocr_done": {"sqlite": "BOOLEAN DEFAULT 0", "mssql": "BIT DEFAULT 0"},
        "classification": {"sqlite": "TEXT DEFAULT ''", "mssql": "NVARCHAR(MAX) DEFAULT ''"},
    },
    "questions": {
        "options": {"sqlite": "TEXT DEFAULT ''", "mssql": "NVARCHAR(MAX) DEFAULT ''"},
        "source": {"sqlite": "VARCHAR(20) DEFAULT 'manual'", "mssql": "VARCHAR(20) DEFAULT 'manual'"},
        "status": {"sqlite": "VARCHAR(20) DEFAULT 'pending'", "mssql": "VARCHAR(20) DEFAULT 'pending'"},
        "ocr_confidence": {"sqlite": "FLOAT DEFAULT 0", "mssql": "FLOAT DEFAULT 0"},
        "frame_confidence": {"sqlite": "FLOAT DEFAULT 0", "mssql": "FLOAT DEFAULT 0"},
        "merge_confidence": {"sqlite": "FLOAT DEFAULT 0", "mssql": "FLOAT DEFAULT 0"},
        "overall_confidence": {"sqlite": "FLOAT DEFAULT 0", "mssql": "FLOAT DEFAULT 0"},
        "frame_start": {"sqlite": "INTEGER", "mssql": "INT"},
        "frame_end": {"sqlite": "INTEGER", "mssql": "INT"},
    },
}


def _sqlite_existing_columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}


def _mssql_existing_columns(conn, table: str) -> set[str]:
    rows = conn.exec_driver_sql(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?", (table,)
    )
    return {row[0] for row in rows}


def _run_additive_column_migration(dialect: str) -> None:
    existing_columns_fn = _sqlite_existing_columns if dialect == "sqlite" else _mssql_existing_columns
    with engine.begin() as conn:
        for table, columns in _NEW_COLUMNS.items():
            existing = existing_columns_fn(conn, table)
            for name, ddl_by_dialect in columns.items():
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD {name} {ddl_by_dialect[dialect]}")


def init_db() -> None:
    from app import models  # noqa: F401  (register mappers)

    if engine.dialect.name == "mssql":
        from app.database.mssql_bootstrap import bootstrap

        bootstrap(engine)

    Base.metadata.create_all(bind=engine)

    # Additive-column migration: create_all() only creates missing tables, so
    # columns added to an already-existing table's model (on any dialect,
    # including a SQL Server target initialized before the column existed)
    # need this explicit ALTER TABLE pass. Runs on both SQLite and SQL Server;
    # structural (non-additive) changes still use Alembic later.
    if engine.dialect.name in ("sqlite", "mssql"):
        _run_additive_column_migration(engine.dialect.name)

    from app.database.migrations import MIGRATIONS, run_pending
    from app.shared.logging import get_logger

    get_logger("migrations").info("Checking migrations...")
    run_pending(engine, MIGRATIONS)
