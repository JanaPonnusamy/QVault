from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.video import Video


class VideoRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, video_id: int) -> Video | None:
        return self.db.get(Video, video_id)

    def add(self, video: Video) -> Video:
        self.db.add(video)
        self.db.commit()
        self.db.refresh(video)
        return video

    def save(self) -> None:
        self.db.commit()

    def delete(self, video: Video) -> None:
        self.db.delete(video)
        self.db.commit()

    def query(
        self,
        search: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        template: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[Video], int]:
        stmt = select(Video)
        if search:
            stmt = stmt.where(func.lower(Video.title).like(f"%{search.lower()}%"))
        if kind:
            stmt = stmt.where(Video.kind == kind)
        if status:
            stmt = stmt.where(Video.status == status)
        if template:
            stmt = stmt.where(Video.template == template)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = stmt.order_by(Video.id.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt)), int(total)

    def stats(self) -> dict:
        total = self.db.scalar(select(func.count(Video.id))) or 0
        by_status = dict(
            self.db.execute(select(Video.status, func.count(Video.id)).group_by(Video.status)).all()
        )
        by_kind = dict(
            self.db.execute(select(Video.kind, func.count(Video.id)).group_by(Video.kind)).all()
        )
        total_seconds = (
            self.db.scalar(select(func.sum(Video.duration)).where(Video.status == "completed")) or 0
        )
        total_bytes = (
            self.db.scalar(select(func.sum(Video.file_size)).where(Video.status == "completed")) or 0
        )
        return {
            "total": int(total),
            "completed": int(by_status.get("completed", 0)),
            "failed": int(by_status.get("failed", 0)),
            "in_progress": int(by_status.get("rendering", 0) + by_status.get("queued", 0)),
            "videos": int(by_kind.get("video", 0)),
            "shorts": int(by_kind.get("short", 0)),
            "reels": int(by_kind.get("reel", 0)),
            "total_duration": float(total_seconds),
            "total_size": int(total_bytes),
        }
