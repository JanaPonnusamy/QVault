"""Question JSON discovery + loading for the video generation engine.

Scans ``storage/**/*.json`` for files that match the existing Question schema
(a list of objects carrying ``question`` / ``options`` / ``answer``) and
normalizes entries into render-ready :class:`QuestionItem` rows. The schema is
reused as-is — no re-extraction, no schema changes.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from app.config.settings import settings
from app.shared.logging import get_logger

logger = get_logger("video_source")

MAX_OPTIONS = 4  # the 2-per-row option grid renders up to 4 options


@dataclass
class QuestionItem:
    id: str
    question: str
    options: list[str]
    answer_index: int
    solution: str
    topic: str

    @property
    def answer_text(self) -> str:
        return self.options[self.answer_index]


@dataclass
class SourceFile:
    path: str  # relative to storage_dir, POSIX-style
    question_count: int
    usable_count: int
    topics: dict[str, int] = field(default_factory=dict)


def _normalize(raw: dict) -> QuestionItem | None:
    question = str(raw.get("question") or "").strip()
    if question and question[0].islower():
        question = question[0].upper() + question[1:]
    options = [str(o).strip() for o in raw.get("options") or [] if str(o).strip()]
    answer = str(raw.get("answer") or "").strip()
    if not question or not answer or len(options) < 2 or len(options) > MAX_OPTIONS:
        return None
    try:
        answer_index = [o.casefold() for o in options].index(answer.casefold())
    except ValueError:
        return None
    return QuestionItem(
        id=str(raw.get("id") or ""),
        question=question,
        options=options,
        answer_index=answer_index,
        solution=str(raw.get("solution") or "").strip(),
        topic=str(raw.get("topic") or "General Knowledge").strip() or "General Knowledge",
    )


def _read_questions(path: Path) -> list[QuestionItem]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):  # exports wrap rows under "questions"
        data = data.get("questions", [])
    if not isinstance(data, list):
        return []
    items = []
    for raw in data:
        if isinstance(raw, dict):
            item = _normalize(raw)
            if item:
                items.append(item)
    return items


class VideoSourceService:
    """Catalog + selection over question JSON files under ``storage/``."""

    def list_sources(self) -> list[SourceFile]:
        sources: list[SourceFile] = []
        for path in sorted(settings.storage_dir.rglob("*.json")):
            # knowledge research artifacts are JSON but not question banks;
            # cheap shape check inside _read_questions filters them out.
            items = _read_questions(path)
            if not items:
                continue
            raw_count = self._raw_count(path)
            topics: dict[str, int] = {}
            for item in items:
                topics[item.topic] = topics.get(item.topic, 0) + 1
            sources.append(
                SourceFile(
                    path=path.relative_to(settings.storage_dir).as_posix(),
                    question_count=raw_count,
                    usable_count=len(items),
                    topics=dict(sorted(topics.items(), key=lambda kv: -kv[1])),
                )
            )
        return sources

    @staticmethod
    def _raw_count(path: Path) -> int:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return 0
        if isinstance(data, dict):
            data = data.get("questions", [])
        return len(data) if isinstance(data, list) else 0

    def load(
        self,
        source_file: str,
        topic: str | None = None,
        count: int = 25,
        offset: int = 0,
        shuffle_seed: int | None = None,
    ) -> list[QuestionItem]:
        path = (settings.storage_dir / source_file).resolve()
        if not path.is_relative_to(settings.storage_dir.resolve()):
            raise ValueError("Source file must live under storage/")
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {source_file}")
        items = _read_questions(path)
        if topic:
            items = [i for i in items if i.topic.casefold() == topic.casefold()]
        if shuffle_seed is not None:
            random.Random(shuffle_seed).shuffle(items)
        selected = items[offset : offset + count]
        if not selected:
            raise ValueError("No usable questions matched the selection")
        return selected
