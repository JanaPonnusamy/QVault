from sqlalchemy import select

from app.database.migrations import MIGRATIONS
from app.database.session import SessionLocal, engine
from app.models.system import DatabaseVersion


def get_health_status() -> dict:
    database: dict = {
        "backend": engine.dialect.name,
        "reachable": False,
        "database_exists": False,
    }
    migrations: dict = {
        "total": len(MIGRATIONS),
        "applied": 0,
        "pending": len(MIGRATIONS),
        "pending_names": [m.name for m in MIGRATIONS],
        "last_migration": None,
    }

    try:
        with SessionLocal() as db:
            db.execute(select(1))
            database["reachable"] = True
            database["database_exists"] = True

            applied_names = set(
                db.execute(
                    select(DatabaseVersion.migration_name).where(DatabaseVersion.status == "success")
                )
                .scalars()
                .all()
            )
            migrations["applied"] = len(applied_names)
            migrations["pending_names"] = [m.name for m in MIGRATIONS if m.name not in applied_names]
            migrations["pending"] = len(migrations["pending_names"])

            last = db.execute(
                select(DatabaseVersion).order_by(DatabaseVersion.applied_on.desc()).limit(1)
            ).scalar_one_or_none()
            if last is not None:
                migrations["last_migration"] = {
                    "name": last.migration_name,
                    "applied_on": last.applied_on.isoformat(),
                    "status": last.status,
                }
    except Exception as exc:
        database["error"] = str(exc)

    bootstrap_ok = database["reachable"] and migrations["pending"] == 0

    return {
        "status": "ok" if bootstrap_ok else ("degraded" if database["reachable"] else "error"),
        "database": database,
        "migrations": migrations,
        "bootstrap_status": "complete" if bootstrap_ok else "pending",
    }
