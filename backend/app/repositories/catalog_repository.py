from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.integrations.syllabus_pdf_parser import ParsedSubject
from app.models.catalog import Chapter, Exam, Subject, Topic, Unit


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return (slug or "item")[:max_len]


def _unique_code(title: str, used: set[str], max_len: int = 40) -> str:
    """Slugify title into a code unique within `used` (siblings under one parent).

    Two differently-worded siblings that happen to slugify identically must
    not collapse into a single row, so collisions get a numeric suffix.
    Deterministic given the same input order, so re-importing the same PDF
    reproduces the same codes (true idempotency, not just dedup-by-luck).
    The numeric suffix is reserved for up front so `base + suffix` never
    exceeds `max_len` (a truncated base plus suffix previously could).
    """
    base = _slugify(title, max_len)
    code = base
    n = 2
    while code in used:
        suffix = f"_{n}"
        code = base[: max_len - len(suffix)] + suffix
        n += 1
    used.add(code)
    return code


class CatalogRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---------- reads ----------

    def list_exams(self) -> list[Exam]:
        stmt = select(Exam).where(Exam.is_deleted == False)  # noqa: E712
        return list(self.db.scalars(stmt.order_by(Exam.display_order, Exam.name)))

    def get_exam(self, exam_id: uuid.UUID) -> Exam | None:
        exam = self.db.get(Exam, exam_id)
        return exam if exam and not exam.is_deleted else None

    def get_exam_by_code(self, code: str) -> Exam | None:
        stmt = select(Exam).where(Exam.code == code, Exam.is_deleted == False)  # noqa: E712
        return self.db.scalars(stmt).first()

    def list_subjects(self, exam_id: uuid.UUID) -> list[Subject]:
        stmt = select(Subject).where(Subject.exam_id == exam_id, Subject.is_deleted == False)  # noqa: E712
        return list(self.db.scalars(stmt.order_by(Subject.display_order, Subject.name)))

    def get_subject(self, subject_id: uuid.UUID) -> Subject | None:
        subject = self.db.get(Subject, subject_id)
        return subject if subject and not subject.is_deleted else None

    def list_units(self, subject_id: uuid.UUID) -> list[Unit]:
        stmt = select(Unit).where(Unit.subject_id == subject_id, Unit.is_deleted == False)  # noqa: E712
        return list(self.db.scalars(stmt.order_by(Unit.display_order, Unit.name)))

    def get_unit(self, unit_id: uuid.UUID) -> Unit | None:
        unit = self.db.get(Unit, unit_id)
        return unit if unit and not unit.is_deleted else None

    def list_chapters(self, unit_id: uuid.UUID) -> list[Chapter]:
        stmt = select(Chapter).where(Chapter.unit_id == unit_id, Chapter.is_deleted == False)  # noqa: E712
        return list(self.db.scalars(stmt.order_by(Chapter.display_order, Chapter.name)))

    def get_chapter(self, chapter_id: uuid.UUID) -> Chapter | None:
        chapter = self.db.get(Chapter, chapter_id)
        return chapter if chapter and not chapter.is_deleted else None

    def list_topics(self, chapter_id: uuid.UUID) -> list[Topic]:
        stmt = select(Topic).where(Topic.chapter_id == chapter_id, Topic.is_deleted == False)  # noqa: E712
        return list(self.db.scalars(stmt.order_by(Topic.display_order, Topic.name)))

    def exam_tree(self, exam_id: uuid.UUID) -> Exam | None:
        stmt = (
            select(Exam)
            .where(Exam.id == exam_id, Exam.is_deleted == False)  # noqa: E712
            .options(
                selectinload(Exam.subjects)
                .selectinload(Subject.units)
                .selectinload(Unit.chapters)
                .selectinload(Chapter.topics)
            )
        )
        return self.db.scalars(stmt).first()

    def stats(self) -> dict:
        return {
            "exams": self.db.scalar(select(func.count()).select_from(Exam).where(Exam.is_deleted == False)) or 0,  # noqa: E712
            "subjects": self.db.scalar(select(func.count()).select_from(Subject).where(Subject.is_deleted == False)) or 0,  # noqa: E712
            "units": self.db.scalar(select(func.count()).select_from(Unit).where(Unit.is_deleted == False)) or 0,  # noqa: E712
            "chapters": self.db.scalar(select(func.count()).select_from(Chapter).where(Chapter.is_deleted == False)) or 0,  # noqa: E712
            "topics": self.db.scalar(select(func.count()).select_from(Topic).where(Topic.is_deleted == False)) or 0,  # noqa: E712
        }

    # ---------- syllabus import upsert ----------

    def upsert_syllabus(
        self,
        exam_code: str,
        exam_name: str,
        parsed_subjects: list[ParsedSubject],
        user_id: int | None,
    ) -> dict[str, int]:
        """Create-or-update the exam's hierarchy from a parsed syllabus.

        Idempotent by (parent, code): re-importing the same PDF updates
        names/ordering in place rather than duplicating rows. Codes are
        slugified from titles, so the same title always maps to the same
        row under the same parent.
        """
        counts = {
            "subjects": 0, "units": 0, "chapters": 0, "topics": 0,
            "created": 0, "updated": 0,
        }

        exam = self.get_exam_by_code(exam_code)
        if exam is None:
            exam = Exam(code=exam_code, name=exam_name, created_by=user_id, modified_by=user_id)
            self.db.add(exam)
            self.db.flush()
            counts["created"] += 1
        elif exam.name != exam_name:
            exam.name = exam_name
            exam.modified_by = user_id
            counts["updated"] += 1

        used_subject_codes: set[str] = set()
        for s_order, parsed_subject in enumerate(parsed_subjects):
            subject_code = _unique_code(parsed_subject.title, used_subject_codes)
            subject = self._upsert(
                Subject, {"exam_id": exam.id}, subject_code, parsed_subject.title, s_order, user_id, counts,
            )
            counts["subjects"] += 1

            used_unit_codes: set[str] = set()
            for u_order, parsed_unit in enumerate(parsed_subject.units):
                unit_code = _unique_code(parsed_unit.title, used_unit_codes)
                unit = self._upsert(
                    Unit, {"subject_id": subject.id}, unit_code, parsed_unit.title, u_order, user_id, counts,
                )
                counts["units"] += 1

                used_chapter_codes: set[str] = set()
                for c_order, parsed_chapter in enumerate(parsed_unit.chapters):
                    chapter_code = _unique_code(parsed_chapter.title, used_chapter_codes)
                    chapter = self._upsert(
                        Chapter, {"unit_id": unit.id}, chapter_code, parsed_chapter.title, c_order, user_id, counts,
                    )
                    counts["chapters"] += 1

                    used_topic_codes: set[str] = set()
                    for t_order, parsed_topic in enumerate(parsed_chapter.topics):
                        topic_code = _unique_code(parsed_topic.title, used_topic_codes)
                        self._upsert(
                            Topic, {"chapter_id": chapter.id}, topic_code, parsed_topic.title, t_order, user_id, counts,
                        )
                        counts["topics"] += 1

        self.db.commit()
        return counts

    def _upsert(
        self, model, parent_filter: dict, code: str, title: str, order: int, user_id: int | None, counts: dict,
    ):
        """Find-by-(parent, code) or create; update name/display_order in place."""
        stmt = select(model).filter_by(**parent_filter, code=code)
        row = self.db.scalars(stmt).first()
        if row is None:
            row = model(
                code=code,
                name=title[:400],
                display_order=order,
                created_by=user_id,
                modified_by=user_id,
                **parent_filter,
            )
            self.db.add(row)
            self.db.flush()
            counts["created"] += 1
        else:
            changed = row.name != title[:400] or row.display_order != order
            row.name = title[:400]
            row.display_order = order
            if changed:
                row.modified_by = user_id
                counts["updated"] += 1
        return row
