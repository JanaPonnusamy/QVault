"""One-time backfill: import questions already scraped by the legacy standalone
scrapers (D:\\VBDOTNET\\tnpsc) into the Question Bank, so the live GK Scraper
module only has to catch what's genuinely new instead of re-crawling sites like
examveda from scratch. Uses the same `QuestionBankService.create()` path (and
therefore the same per-provider question_hash duplicate check) as the live
scraper, and `provider` is set to match the live provider's own naming
(`gk_<domain>`) so future crawls of the same site share one duplicate scope
with this import.

Large files (indiabix, 270MB+) are streamed with ijson instead of json.load to
avoid loading the whole array into memory.

Run manually — nothing schedules this automatically:
    cd backend && python scripts/import_legacy_gk_json.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ijson  # noqa: E402

from app.database.session import SessionLocal  # noqa: E402
from app.services.question_bank_service import QuestionBankService  # noqa: E402
from app.shared.logging import get_logger  # noqa: E402

logger = get_logger("import_legacy_gk_json")

CATEGORY = "General Knowledge"
LEGACY_ROOT = Path(r"D:\VBDOTNET\tnpsc\data\questions")

# Each source: legacy file -> provider/website to file it under. `provider`
# matches the live GkWebsiteProvider naming (`gk_<domain>`) where the site is
# also crawled live, so the two share one duplicate scope going forward.
SOURCES = [
    {
        "file": LEGACY_ROOT / "examveda_all_questions.json",
        "provider": "gk_www.examveda.com",
        "website": "https://www.examveda.com",
        "streaming": False,
        "answer_key": "answer",
        "solution_key": "solution",
    },
    {
        "file": LEGACY_ROOT / "indiabix" / "indiabix_all_questions.json",
        "provider": "gk_www.indiabix.com",
        "website": "https://www.indiabix.com",
        "streaming": True,
        "answer_key": "answer",
        "solution_key": "explanation",
    },
    {
        "file": LEGACY_ROOT / "state_gk" / "tamilnadu_gk.json",
        "provider": "legacy_tamilnadu_gk",
        "website": "",
        "streaming": False,
        "answer_key": "answer",
        "solution_key": "solution",
    },
]


def _iter_records(path: Path, streaming: bool) -> Iterator[dict]:
    if streaming:
        with path.open("rb") as f:
            yield from ijson.items(f, "item")
    else:
        with path.open("r", encoding="utf-8") as f:
            yield from json.load(f)


def _build_options(raw_options: list[str], answer: str) -> tuple[list[dict], bool]:
    answer_norm = (answer or "").strip().lower()
    matches = [o for o in raw_options if o.strip().lower() == answer_norm]
    matched = len(matches) == 1
    return (
        [
            {"label": chr(65 + i), "text": text, "is_correct": matched and text.strip().lower() == answer_norm}
            for i, text in enumerate(raw_options)
        ],
        matched,
    )


_COMMIT_BATCH_SIZE = 300


def import_source(qb: QuestionBankService, source: dict, dry_run: bool) -> tuple[int, int, int]:
    path: Path = source["file"]
    if not path.exists():
        logger.warning("Skipping missing file: %s", path)
        return 0, 0, 0

    processed = created = skipped_bad = 0
    source_payload = {
        "provider": source["provider"],
        "url": f"legacy-import://{source['provider']}",
        "website": source["website"],
        "exam": CATEGORY,
    }

    for record in _iter_records(path, source["streaming"]):
        question_text = (record.get("question") or "").strip()
        raw_options = [o for o in (record.get("options") or []) if isinstance(o, str) and o.strip()]
        answer = (record.get(source["answer_key"]) or "").strip()
        if not question_text or len(raw_options) < 2:
            skipped_bad += 1
            continue

        options, matched = _build_options(raw_options, answer)
        processed += 1
        if dry_run:
            continue

        record_url = record.get("url")
        payload = dict(source_payload)
        if record_url:
            payload["url"] = record_url

        question = qb.create(
            question_text=question_text,
            exam=CATEGORY,
            question_type="mcq",
            correct_answer_text=answer if matched else "",
            status="draft" if matched else "pending_review",
            confidence=0.85 if matched else 0.5,
            options=options,
            solution_text=(record.get(source["solution_key"]) or "").strip(),
            solution_source_type="scraped",
            source=payload,
            commit=False,
        )
        if not getattr(question, "was_skipped_as_duplicate", False):
            created += 1

        # Commit in small batches, not once for the whole file: at file scale
        # (tens/hundreds of thousands of rows) a single end-of-file commit
        # keeps one transaction open long enough for SQL Server to escalate
        # to a table-level lock, which then blocks every other query against
        # bank_questions/bank_sources -- including the live GK scraper's own
        # saves and the site-reports endpoint (confirmed live: the frontend
        # started 500ing on site-reports while an earlier single-commit run
        # of this script was mid-way through examveda).
        if not dry_run and processed % _COMMIT_BATCH_SIZE == 0:
            qb.db.commit()

    if not dry_run:
        qb.db.commit()
    return processed, created, skipped_bad


def run(dry_run: bool) -> None:
    db = SessionLocal()
    try:
        qb = QuestionBankService(db)
        total_processed = total_created = total_bad = 0
        for source in SOURCES:
            processed, created, skipped_bad = import_source(qb, source, dry_run)
            total_processed += processed
            total_created += created
            total_bad += skipped_bad
            logger.info(
                "%s: processed=%d created=%d skipped_malformed=%d",
                source["file"], processed, created, skipped_bad,
            )
        logger.info(
            "TOTAL: processed=%d created=%d (duplicates skipped=%d) skipped_malformed=%d%s",
            total_processed, total_created, total_processed - total_created, total_bad,
            " [DRY RUN]" if dry_run else "",
        )
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Count records without writing to the DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
