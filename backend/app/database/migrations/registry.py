"""Ordered list of all migrations ever written. Never edit or remove an
existing entry — append new ones. The runner tracks completion by name in
system.database_version, so removing/renaming an entry would cause it to
re-run (or an already-applied one to look pending)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.migrations.runner import Migration
from app.models.mixins import DEFAULT_TENANT_ID
from app.models.system import Tenant


def _seed_default_tenant(db: Session) -> None:
    if db.get(Tenant, DEFAULT_TENANT_ID) is not None:
        return
    db.add(
        Tenant(
            tenant_id=DEFAULT_TENANT_ID,
            tenant_code="default",
            tenant_name="Default Tenant",
            active=True,
        )
    )


MIGRATIONS: list[Migration] = [
    Migration(
        name="0001_seed_default_tenant",
        description="Seed the single default tenant referenced by TenantAuditMixin.tenant_id.",
        fn=_seed_default_tenant,
    ),
]
