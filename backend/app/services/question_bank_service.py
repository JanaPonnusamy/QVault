import hashlib
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.question_bank import (
    BankQuestion,
    BankQuestionLineage,
    BankQuestionOption,
    BankQuestionSolution,
    BankQuestionTopic,
)
from app.repositories.question_bank_repository import QuestionBankRepository

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s]")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = _PUNCTUATION.sub("", text)
    text = _WHITESPACE.sub(" ", text)
    return text


def question_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:32]


def _topic_rows(question_id: uuid.UUID, topics: list[dict]) -> list[BankQuestionTopic]:
    return [
        BankQuestionTopic(
            question_id=question_id,
            subject_id=t.get("subject_id"),
            unit_id=t.get("unit_id"),
            chapter_id=t.get("chapter_id"),
            topic_id=t.get("topic_id"),
            is_primary=bool(t.get("is_primary", False)),
        )
        for t in topics
    ]


def _option_rows(question_id: uuid.UUID, options: list[dict]) -> list[BankQuestionOption]:
    return [
        BankQuestionOption(
            question_id=question_id,
            label=opt.get("label", ""),
            text=opt.get("text", ""),
            image_path=opt.get("image_path", ""),
            is_correct=bool(opt.get("is_correct", False)),
            order_index=idx,
        )
        for idx, opt in enumerate(options)
    ]


class QuestionBankService:
    """Deterministic CRUD over the question repository. Duplicate detection here
    is a normalized-text hash match (Phase 1); the future extraction engine adds
    option/image/semantic similarity on top without changing this table. Every
    create/edit/status-change is logged to BankQuestionLineage."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = QuestionBankRepository(db)

    def _options_match(self, question_id: uuid.UUID, new_options: list[dict]) -> bool:
        existing = self.repo.get_options(question_id)
        if len(existing) != len(new_options):
            return False
        existing_set = {(normalize_text(o.text), bool(o.is_correct)) for o in existing}
        new_set = {(normalize_text(o.get("text", "")), bool(o.get("is_correct", False))) for o in new_options}
        return existing_set == new_set

    def create(
        self,
        *,
        question_text: str,
        exam: str = "",
        exam_id: uuid.UUID | None = None,
        year: int | None = None,
        session: str = "",
        shift: str = "",
        difficulty: str = "",
        question_type: str = "mcq",
        language: str = "en",
        correct_answer_text: str = "",
        answer_data: str = "",
        image_exists: bool = False,
        image_path: str = "",
        status: str = "draft",
        confidence: float = 0.0,
        topics: list[dict] | None = None,
        options: list[dict] | None = None,
        solution_text: str = "",
        solution_source_type: str = "manual",
        source: dict | None = None,
        created_by: int | None = None,
        commit: bool = True,
    ) -> BankQuestion:
        """`commit=False` lets a caller batch several `create()` calls (e.g. every
        question extracted from one scraped page) into a single DB round trip —
        see `GkScraperService._save_elements`, which processes a whole page's
        worth of questions and commits once instead of once per question."""
        norm = normalize_text(question_text)
        h = question_hash(question_text)
        provider = (source or {}).get("provider", "")
        # Duplicate scope is per-site (provider), not global: two different
        # GK sites are allowed to carry the identical question (each keeps
        # its own row + source lineage) — only a repeat from the SAME site
        # counts as a true duplicate. Manual entries (no source) still use
        # the old global check since there's no site to scope by.
        duplicate = self.repo.find_by_hash_for_provider(h, provider) if provider else self.repo.find_by_hash(h)

        # Same normalized question AND same options (e.g. the identical GK
        # item re-appearing on a different compilation page of the SAME site,
        # or a page re-scraped after its site changed unrelated content) is a
        # true repeat, not a new draft: skip the insert entirely and just
        # touch the source's crawl_count/last_seen so acquisition history
        # still reflects the re-visit. A hash match with *different* options
        # is kept as a flagged duplicate below, since that's a real edit
        # worth a human's review rather than noise to silently drop.
        if duplicate and self._options_match(duplicate.id, options or []):
            if source and source.get("url"):
                self.repo.get_or_create_source(
                    provider=source.get("provider", "manual"),
                    url=source["url"],
                    defaults={k: v for k, v in source.items() if k not in ("provider", "url")},
                    commit=commit,
                )
            elif commit:
                self.db.commit()
            duplicate.was_skipped_as_duplicate = True
            return duplicate

        source_obj = None
        if source and source.get("url"):
            source_obj = self.repo.get_or_create_source(
                provider=source.get("provider", "manual"),
                url=source["url"],
                defaults={k: v for k, v in source.items() if k not in ("provider", "url")},
                commit=False,
            )

        question = BankQuestion(
            exam=exam,
            exam_id=exam_id,
            year=year,
            session=session,
            shift=shift,
            difficulty=difficulty,
            question_type=question_type,
            question_text=question_text,
            normalized_text=norm,
            language=language,
            correct_answer_text=correct_answer_text,
            answer_data=answer_data,
            image_exists=image_exists,
            image_path=image_path,
            status=status,
            confidence=confidence,
            question_hash=h,
            duplicate_score=1.0 if duplicate else 0.0,
            source_id=source_obj.id if source_obj else None,
            current_stage="acquired" if source_obj else "draft_entry",
            created_by=created_by,
            modified_by=created_by,
        )
        # commit=False on every sub-write below: a single question can mean
        # 5-6 round trips to the DB (question + topics + options + solution +
        # lineage + source touch) — at scraper scale (thousands of pages) that
        # serialized per-row commit cost was the actual bottleneck (measured
        # ~0.35s per question), not network fetch. One commit at the end
        # keeps identical semantics (still one atomic write per question) at
        # a fraction of the round trips.
        self.repo.add(question, commit=False)

        if topics:
            self.repo.replace_topics(question.id, _topic_rows(question.id, topics), commit=False)
        if options:
            self.repo.replace_options(question.id, _option_rows(question.id, options), commit=False)
        if solution_text:
            self.repo.add_solution(
                BankQuestionSolution(
                    question_id=question.id, solution_text=solution_text, source_type=solution_source_type
                ),
                commit=False,
            )

        self.repo.add_lineage(
            BankQuestionLineage(
                question_id=question.id,
                stage=question.current_stage,
                detail="Created via acquisition source" if source_obj else "Created via manual entry",
                created_by=created_by,
            ),
            commit=False,
        )

        if commit:
            self.db.commit()
            self.db.refresh(question)
        else:
            self.db.flush()
        return question

    def update(
        self,
        question: BankQuestion,
        updates: dict,
        topics: list[dict] | None = None,
        options: list[dict] | None = None,
        user_id: int | None = None,
    ) -> BankQuestion:
        if updates.get("question_text"):
            updates["normalized_text"] = normalize_text(updates["question_text"])
            updates["question_hash"] = question_hash(updates["question_text"])
            duplicate = self.repo.find_by_hash(updates["question_hash"], exclude_id=question.id)
            updates["duplicate_score"] = 1.0 if duplicate else 0.0

        for key, value in updates.items():
            if value is not None and hasattr(question, key):
                setattr(question, key, value)
        question.modified_by = user_id
        question.current_stage = "human_corrected"
        self.repo.save()

        if topics is not None:
            self.repo.replace_topics(question.id, _topic_rows(question.id, topics))
        if options is not None:
            self.repo.replace_options(question.id, _option_rows(question.id, options))

        self.repo.add_lineage(
            BankQuestionLineage(
                question_id=question.id, stage="human_corrected", detail="Edited via admin UI", created_by=user_id
            )
        )
        self.db.refresh(question)
        return question

    def set_status(self, question: BankQuestion, status: str, user_id: int | None = None) -> BankQuestion:
        question.status = status
        question.modified_by = user_id
        stage = {"approved": "published", "rejected": "rejected"}.get(status, status)
        question.current_stage = stage
        self.repo.save()
        self.repo.add_lineage(
            BankQuestionLineage(
                question_id=question.id, stage=stage, detail=f"Status set to {status}", created_by=user_id
            )
        )
        return question

    def add_solution(
        self, question_id: uuid.UUID, solution_text: str, explanation: str, source_type: str, source_url: str
    ) -> BankQuestionSolution:
        return self.repo.add_solution(
            BankQuestionSolution(
                question_id=question_id,
                solution_text=solution_text,
                explanation=explanation,
                source_type=source_type,
                source_url=source_url,
            )
        )

    def delete(self, question: BankQuestion) -> None:
        self.repo.delete(question)
