"""Generic migration runner.

A migration is a named, idempotent Python callable operating on a Session.
`run_pending` is dialect-agnostic (works for SQLite and SQL Server alike) and
is the *only* sanctioned way future database changes should be applied —
per CLAUDE.md, ad-hoc DDL/data changes outside this framework are not allowed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.shared.logging import get_logger

logger = get_logger("migrations")


@dataclass(frozen=True)
class Migration:
    name: str
    description: str
    fn: Callable[[Session], None]


def run_pending(engine: Engine, migrations: list[Migration]) -> None:
    from app.database.session import SessionLocal
    from app.models.system import DatabaseVersion

    with SessionLocal() as db:
        applied = set(
            db.execute(
                select(DatabaseVersion.migration_name).where(DatabaseVersion.status == "success")
            )
            .scalars()
            .all()
        )
        next_version = (db.execute(select(DatabaseVersion.version)).scalars().all() or [0])
        next_version = (max(next_version) if next_version else 0) + 1

    pending = [m for m in migrations if m.name not in applied]
    if not pending:
        logger.info("No pending migrations (%d already applied).", len(applied))
        return

    logger.info("Checking migrations... %d pending.", len(pending))
    for migration in pending:
        db = SessionLocal()
        started = time.perf_counter()
        try:
            migration.fn(db)
            db.commit()
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            db.add(
                DatabaseVersion(
                    version=next_version,
                    migration_name=migration.name,
                    execution_time=elapsed_ms,
                    status="success",
                )
            )
            db.commit()
            logger.info("Migration completed: '%s' (%dms).", migration.name, elapsed_ms)
            next_version += 1
        except Exception as exc:
            db.rollback()
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.error("Migration failed: '%s' after %dms: %s", migration.name, elapsed_ms, exc)
            try:
                db.add(
                    DatabaseVersion(
                        version=next_version,
                        migration_name=migration.name,
                        execution_time=elapsed_ms,
                        status="failed",
                        error=str(exc)[:2000],
                    )
                )
                db.commit()
            except Exception:
                db.rollback()
            db.close()
            raise
        finally:
            db.close()

    logger.info("Migration completed. Startup completed.")
