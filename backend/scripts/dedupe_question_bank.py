"""Permanent maintenance script: removes EXACT duplicate questions from the
Question Bank — same normalized question text AND same options AND same
source site (provider). Two different sites carrying the identical question
are left alone (that's allowed; see QuestionBankService.create's per-provider
duplicate scope). For each duplicate group the earliest-created row is kept
and later ones are deleted, so acquisition history (first_seen) is preserved.

Run manually whenever needed — nothing schedules this automatically:
    cd backend && python scripts/dedupe_question_bank.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import joinedload  # noqa: E402

from app.database.session import SessionLocal  # noqa: E402
from app.models.question_bank import BankQuestion, BankQuestionOption, BankSource  # noqa: E402
from app.services.question_bank_service import normalize_text  # noqa: E402
from app.shared.logging import get_logger  # noqa: E402

logger = get_logger("dedupe_question_bank")


def _option_signature(options: list[BankQuestionOption]) -> tuple:
    return tuple(sorted((normalize_text(o.text), bool(o.is_correct)) for o in options))


def run(dry_run: bool) -> None:
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = SessionLocal()
    try:
        rows = db.execute(
            select(BankQuestion)
            .options(joinedload(BankQuestion.options))
            .outerjoin(BankSource, BankQuestion.source_id == BankSource.id)
            .add_columns(BankSource.provider)
            .order_by(BankQuestion.created_on)
        ).unique().all()

        groups: dict[tuple, list[BankQuestion]] = defaultdict(list)
        for question, provider in rows:
            key = (provider or "manual", question.question_hash, _option_signature(question.options))
            groups[key].append(question)

        to_delete: list[BankQuestion] = []
        for key, questions in groups.items():
            if len(questions) < 2:
                continue
            keep, *rest = questions  # earliest created_on kept (rows are ordered)
            to_delete.extend(rest)
            logger.info(
                "Duplicate group provider=%s hash=%s: keeping %s, removing %d repeat(s)",
                key[0], key[1], keep.id, len(rest),
            )

        logger.info(
            "%s: scanned %d question(s), %d exact same-site duplicate(s) found",
            started, len(rows), len(to_delete),
        )

        if dry_run:
            logger.info("Dry run — no rows deleted.")
            return

        for question in to_delete:
            db.delete(question)
        db.commit()
        logger.info("Deleted %d duplicate question(s).", len(to_delete))
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report duplicates without deleting them")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
