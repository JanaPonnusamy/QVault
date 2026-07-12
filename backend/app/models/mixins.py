import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

# QVault is single-tenant today; every business table still carries tenant_id
# so a future multi-tenant split needs no migration. All rows default to this
# fixed tenant until a tenant management module exists.
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TenantAuditMixin:
    """Common multi-tenant + audit columns shared by every business table."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, default=lambda: DEFAULT_TENANT_ID, index=True)
    created_on: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modified_on: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    modified_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
