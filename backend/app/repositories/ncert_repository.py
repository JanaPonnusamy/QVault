from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.acquisition import NcertBook


class NcertRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, book_id: int) -> NcertBook | None:
        return self.db.get(NcertBook, book_id)

    def get_by_code(self, code: str) -> NcertBook | None:
        return self.db.scalar(select(NcertBook).where(NcertBook.book_code == code))

    def get_many(self, ids: list[int]) -> list[NcertBook]:
        if not ids:
            return []
        return list(self.db.scalars(select(NcertBook).where(NcertBook.id.in_(ids))))

    def add(self, book: NcertBook) -> NcertBook:
        self.db.add(book)
        self.db.commit()
        self.db.refresh(book)
        return book

    def save(self) -> None:
        self.db.commit()

    def query(
        self,
        search: str | None = None,
        class_level: str | None = None,
        subject: str | None = None,
        language: str | None = None,
        status: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[NcertBook], int]:
        stmt = select(NcertBook)
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                func.lower(NcertBook.title).like(like)
                | func.lower(NcertBook.subject).like(like)
                | func.lower(NcertBook.book_code).like(like)
            )
        if class_level:
            stmt = stmt.where(NcertBook.class_level == class_level)
        if subject:
            stmt = stmt.where(NcertBook.subject == subject)
        if language:
            stmt = stmt.where(NcertBook.language == language)
        if status:
            stmt = stmt.where(NcertBook.status == status)

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = stmt.order_by(NcertBook.class_level, NcertBook.subject, NcertBook.title)
        stmt = stmt.limit(limit).offset(offset)
        return list(self.db.scalars(stmt)), int(total)

    def all_missing(self) -> list[NcertBook]:
        return list(
            self.db.scalars(
                select(NcertBook).where(NcertBook.downloaded.is_(False))
            )
        )

    def downloaded_books(self) -> list[NcertBook]:
        return list(
            self.db.scalars(
                select(NcertBook).where(NcertBook.downloaded.is_(True))
            )
        )

    def stats(self) -> dict:
        rows = self.db.execute(
            select(NcertBook.status, func.count()).group_by(NcertBook.status)
        ).all()
        by_status = {status: count for status, count in rows}
        total = sum(by_status.values())
        downloaded = self.db.scalar(
            select(func.count()).select_from(NcertBook).where(NcertBook.downloaded.is_(True))
        ) or 0
        return {
            "total": total,
            "downloaded": int(downloaded),
            "available": by_status.get("available", 0),
            "pending": by_status.get("queued", 0) + by_status.get("downloading", 0),
            "failed": by_status.get("failed", 0),
            "update_available": by_status.get("update_available", 0),
        }

    def distinct(self, column) -> list[str]:
        rows = self.db.scalars(select(column).distinct().order_by(column)).all()
        return [r for r in rows if r]
