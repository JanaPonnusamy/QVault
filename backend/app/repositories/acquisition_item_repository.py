from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.acquisition import AcquisitionItem


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AcquisitionItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, item_id: int) -> AcquisitionItem | None:
        return self.db.get(AcquisitionItem, item_id)

    def find(self, provider: str, source_id: str) -> AcquisitionItem | None:
        stmt = select(AcquisitionItem).where(
            AcquisitionItem.provider == provider, AcquisitionItem.source_id == source_id
        )
        return self.db.scalar(stmt)

    def save(self, item: AcquisitionItem, commit: bool = True) -> AcquisitionItem:
        self.db.add(item)
        if commit:
            self.db.commit()
            self.db.refresh(item)
        else:
            self.db.flush()
        return item

    def delete(self, item: AcquisitionItem) -> None:
        self.db.delete(item)
        self.db.commit()

    def pending(self, provider: str | None = None, limit: int = 100) -> list[AcquisitionItem]:
        """Items ready to be (re)processed — discovered or eligible for retry.
        This is the resume/checkpoint-recovery read path: a fresh worker just
        calls this instead of re-discovering everything from scratch."""
        stmt = select(AcquisitionItem).where(AcquisitionItem.status.in_(["discovered", "retry"]))
        if provider:
            stmt = stmt.where(AcquisitionItem.provider == provider)
        return list(self.db.scalars(stmt.order_by(AcquisitionItem.discovered_at).limit(limit)))

    def stuck(self, statuses: list[str], older_than_minutes: int) -> list[AcquisitionItem]:
        cutoff = _now() - timedelta(minutes=older_than_minutes)
        stmt = select(AcquisitionItem).where(
            AcquisitionItem.status.in_(statuses), AcquisitionItem.updated_at < cutoff
        )
        return list(self.db.scalars(stmt))

    def list_by_provider(
        self, provider: str, status: str | None = None, limit: int = 50, offset: int = 0,
    ) -> tuple[list[AcquisitionItem], int]:
        """Paginated read of every URL this provider has ever discovered/visited
        (the scraped/visited-URL ledger — reuses AcquisitionItem rather than a
        second table, since one row per (provider, source_id) already carries
        url/status/document_type/checksum/error/timestamps)."""
        stmt = select(AcquisitionItem).where(AcquisitionItem.provider == provider)
        if status:
            stmt = stmt.where(AcquisitionItem.status == status)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = list(
            self.db.scalars(stmt.order_by(AcquisitionItem.updated_at.desc()).offset(offset).limit(limit))
        )
        return rows, total

    def stats(self) -> dict[str, int]:
        rows = self.db.execute(
            select(AcquisitionItem.status, func.count()).group_by(AcquisitionItem.status)
        ).all()
        return {status: count for status, count in rows}
