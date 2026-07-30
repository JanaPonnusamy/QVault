import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.question_bank import (
    BankQuestion,
    BankQuestionLineage,
    BankQuestionOption,
    BankQuestionSolution,
    BankQuestionTopic,
    BankSource,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class QuestionBankRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, question_id: uuid.UUID) -> BankQuestion | None:
        return self.db.get(BankQuestion, question_id)

    def add(self, question: BankQuestion, commit: bool = True) -> BankQuestion:
        self.db.add(question)
        if commit:
            self.db.commit()
            self.db.refresh(question)
        else:
            # Still need the generated PK for FK rows (options/solution/lineage)
            # written in the same logical create — flush without a full commit.
            self.db.flush()
        return question

    def save(self) -> None:
        self.db.commit()

    def delete(self, question: BankQuestion) -> None:
        self.db.delete(question)
        self.db.commit()

    def replace_options(self, question_id: uuid.UUID, options: list[BankQuestionOption], commit: bool = True) -> None:
        self.db.query(BankQuestionOption).filter(BankQuestionOption.question_id == question_id).delete()
        self.db.add_all(options)
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def replace_topics(self, question_id: uuid.UUID, topics: list[BankQuestionTopic], commit: bool = True) -> None:
        self.db.query(BankQuestionTopic).filter(BankQuestionTopic.question_id == question_id).delete()
        self.db.add_all(topics)
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def add_solution(self, solution: BankQuestionSolution, commit: bool = True) -> BankQuestionSolution:
        self.db.add(solution)
        if commit:
            self.db.commit()
            self.db.refresh(solution)
        else:
            self.db.flush()
        return solution

    def delete_solution(self, solution_id: int) -> bool:
        solution = self.db.get(BankQuestionSolution, solution_id)
        if not solution:
            return False
        self.db.delete(solution)
        self.db.commit()
        return True

    def add_lineage(self, entry: BankQuestionLineage, commit: bool = True) -> BankQuestionLineage:
        self.db.add(entry)
        if commit:
            self.db.commit()
            self.db.refresh(entry)
        else:
            self.db.flush()
        return entry

    def lineage(self, question_id: uuid.UUID) -> list[BankQuestionLineage]:
        stmt = (
            select(BankQuestionLineage)
            .where(BankQuestionLineage.question_id == question_id)
            .order_by(BankQuestionLineage.id)
        )
        return list(self.db.scalars(stmt))

    def find_by_hash(self, question_hash: str, exclude_id: uuid.UUID | None = None) -> BankQuestion | None:
        stmt = select(BankQuestion).where(BankQuestion.question_hash == question_hash)
        if exclude_id:
            stmt = stmt.where(BankQuestion.id != exclude_id)
        return self.db.scalar(stmt.limit(1))

    # ---------- sources ----------

    def get_or_create_source(self, provider: str, url: str, defaults: dict, commit: bool = True) -> BankSource:
        """Never overwrite: an existing (provider, url) source is touched
        (crawl_count/last_seen/checksum/last_status) rather than duplicated,
        so acquisition history accumulates instead of resetting."""
        stmt = select(BankSource).where(BankSource.provider == provider, BankSource.url == url)
        source = self.db.scalar(stmt)
        if source:
            source.crawl_count += 1
            source.last_seen = _now()
            for key in ("checksum", "last_status", "exam", "year", "shift", "language", "license", "website"):
                if defaults.get(key) is not None:
                    setattr(source, key, defaults[key])
        else:
            source = BankSource(
                provider=provider,
                url=url,
                first_seen=_now(),
                last_seen=_now(),
                **{k: v for k, v in defaults.items() if v is not None},
            )
            self.db.add(source)
        if commit:
            self.db.commit()
            self.db.refresh(source)
        else:
            self.db.flush()
        return source

    def list_sources(self, limit: int = 50, offset: int = 0) -> tuple[list[BankSource], int]:
        total = self.db.scalar(select(func.count()).select_from(BankSource)) or 0
        stmt = select(BankSource).order_by(BankSource.last_seen.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt)), int(total)

    # ---------- query ----------

    def query(
        self,
        search: str | None = None,
        exam: str | None = None,
        year: int | None = None,
        subject_id: uuid.UUID | None = None,
        unit_id: uuid.UUID | None = None,
        chapter_id: uuid.UUID | None = None,
        topic_id: uuid.UUID | None = None,
        question_type: str | None = None,
        difficulty: str | None = None,
        status: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[BankQuestion], int]:
        stmt = select(BankQuestion)
        needs_topic_join = any(v is not None for v in (subject_id, unit_id, chapter_id, topic_id))
        if needs_topic_join:
            stmt = stmt.join(BankQuestionTopic, BankQuestionTopic.question_id == BankQuestion.id)
            if subject_id is not None:
                stmt = stmt.where(BankQuestionTopic.subject_id == subject_id)
            if unit_id is not None:
                stmt = stmt.where(BankQuestionTopic.unit_id == unit_id)
            if chapter_id is not None:
                stmt = stmt.where(BankQuestionTopic.chapter_id == chapter_id)
            if topic_id is not None:
                stmt = stmt.where(BankQuestionTopic.topic_id == topic_id)

        if search:
            stmt = stmt.where(func.lower(BankQuestion.question_text).like(f"%{search.lower()}%"))
        if exam:
            stmt = stmt.where(BankQuestion.exam == exam)
        if year is not None:
            stmt = stmt.where(BankQuestion.year == year)
        if question_type:
            stmt = stmt.where(BankQuestion.question_type == question_type)
        if difficulty:
            stmt = stmt.where(BankQuestion.difficulty == difficulty)
        if status:
            stmt = stmt.where(BankQuestion.status == status)

        if needs_topic_join:
            stmt = stmt.distinct()

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = stmt.order_by(BankQuestion.created_on.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt)), int(total)

    def stats(self) -> dict:
        rows = self.db.execute(
            select(BankQuestion.status, func.count()).group_by(BankQuestion.status)
        ).all()
        by_status = {status: count for status, count in rows}
        total = sum(by_status.values())

        type_rows = self.db.execute(
            select(BankQuestion.question_type, func.count()).group_by(BankQuestion.question_type)
        ).all()
        by_type = {qtype: count for qtype, count in type_rows}

        with_solution = self.db.scalar(
            select(func.count(func.distinct(BankQuestionSolution.question_id)))
        ) or 0
        with_image = self.db.scalar(
            select(func.count()).select_from(BankQuestion).where(BankQuestion.image_exists == True)  # noqa: E712
        ) or 0
        needs_review = self.db.scalar(
            select(func.count()).select_from(BankQuestion).where(BankQuestion.status == "pending_review")
        ) or 0
        sources = self.db.scalar(select(func.count()).select_from(BankSource)) or 0

        return {
            "total": total,
            "draft": by_status.get("draft", 0),
            "pending_review": by_status.get("pending_review", 0),
            "approved": by_status.get("approved", 0),
            "rejected": by_status.get("rejected", 0),
            "duplicate": by_status.get("duplicate", 0),
            "with_solution": int(with_solution),
            "with_image": int(with_image),
            "needs_review": int(needs_review),
            "sources": int(sources),
            "by_type": by_type,
        }
