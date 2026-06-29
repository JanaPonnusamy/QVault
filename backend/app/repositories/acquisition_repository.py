from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.acquisition import AcquisitionJob, Notification


class AcquisitionJobRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, job_id: int) -> AcquisitionJob | None:
        return self.db.get(AcquisitionJob, job_id)

    def add(self, job: AcquisitionJob) -> AcquisitionJob:
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def save(self) -> None:
        self.db.commit()

    def list(self, source: str, limit: int = 20) -> list[AcquisitionJob]:
        return list(
            self.db.scalars(
                select(AcquisitionJob)
                .where(AcquisitionJob.source == source)
                .order_by(AcquisitionJob.id.desc())
                .limit(limit)
            )
        )

    def active(self, source: str) -> list[AcquisitionJob]:
        return list(
            self.db.scalars(
                select(AcquisitionJob).where(
                    AcquisitionJob.source == source,
                    AcquisitionJob.status.in_(["queued", "scanning", "downloading"]),
                )
            )
        )


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, notification: Notification) -> Notification:
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def list(self, limit: int = 30) -> list[Notification]:
        return list(
            self.db.scalars(
                select(Notification).order_by(Notification.id.desc()).limit(limit)
            )
        )

    def unread_count(self) -> int:
        from sqlalchemy import func

        return int(
            self.db.scalar(
                select(func.count()).select_from(Notification).where(Notification.is_read.is_(False))
            )
            or 0
        )

    def mark_all_read(self) -> None:
        for n in self.db.scalars(select(Notification).where(Notification.is_read.is_(False))):
            n.is_read = True
        self.db.commit()

    def get(self, notification_id: int) -> Notification | None:
        return self.db.get(Notification, notification_id)
