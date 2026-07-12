"""Initialize the QVault SQL Server database.

Idempotent. Run from the backend directory:

    python scripts/init_sqlserver.py

It will:
  1. Create the target database (settings.mssql_database) if it does not exist.
  2. Build the full QVault schema (SQLAlchemy create_all) on SQL Server.
  3. Seed permissions, the Super Admin role and the admin user.

Connection settings come from app.config.settings (env prefix QVAULT_, e.g.
QVAULT_MSSQL_SERVER, QVAULT_MSSQL_PASSWORD). This script forces the SQL Server
backend regardless of QVAULT_DB_BACKEND.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the backend package root is importable, and force the SQL Server backend.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["QVAULT_DB_BACKEND"] = "sqlserver"

import pyodbc  # noqa: E402

from app.config.settings import settings  # noqa: E402


def create_database_if_absent() -> bool:
    conn = pyodbc.connect(settings.mssql_master_odbc_connect, autocommit=True)
    try:
        cur = conn.cursor()
        if cur.execute("SELECT db_id(?)", settings.mssql_database).fetchone()[0] is not None:
            print(f"[ok] Database '{settings.mssql_database}' already exists.")
            return False
        cur.execute(f"CREATE DATABASE [{settings.mssql_database}]")
        print(f"[ok] Created database '{settings.mssql_database}'.")
        return True
    finally:
        conn.close()


def main() -> int:
    print(f"Target: {settings.mssql_server},{settings.mssql_port} / {settings.mssql_database}")
    create_database_if_absent()

    # Import after the database exists so the engine connects successfully.
    from app.core.seed import seed
    from app.database.session import engine, init_db

    init_db()
    seed()

    from sqlalchemy import inspect

    tables = sorted(inspect(engine).get_table_names())
    print(f"[ok] Schema ready on {engine.dialect.name}: {len(tables)} tables.")
    for table in tables:
        print(f"     - {table}")
    print("[done] QVault SQL Server database initialized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
