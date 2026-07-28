"""Deterministic, config-driven syllabus PDF -> hierarchy parser.

No AI, no hardcoded exam. `SyllabusParseConfig` supplies the pattern rules
(what a Subject/Unit/Chapter header line looks like) for one exam's official
syllabus PDF layout; the parser itself only ever sees generic text lines.
Adding a new exam is a new `SyllabusParseConfig`, never a code change here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class ParsedTopic:
    title: str


@dataclass
class ParsedChapter:
    title: str
    topics: list[ParsedTopic] = field(default_factory=list)


@dataclass
class ParsedUnit:
    title: str
    chapters: list[ParsedChapter] = field(default_factory=list)


@dataclass
class ParsedSubject:
    title: str
    units: list[ParsedUnit] = field(default_factory=list)


@dataclass
class SyllabusParseConfig:
    """Pattern rules describing one exam's syllabus PDF layout.

    - subject_pattern: matches a line that starts a new Subject.
    - unit_pattern: matches a line that starts a new Unit; group 1 = number
      (ignored), group 2 = title (may be empty, falls back to the whole line).
    - chapter_pattern: optional; when the source PDF has an explicit Chapter
      level, match it with a capturing group 1 for the title. When None
      (e.g. NEET, which only has Unit -> topics), each Unit gets a single
      implicit Chapter that mirrors its own title, keeping the catalog's
      Unit -> Chapter -> Topic depth uniform across exams.
    - topic_split_pattern: how a block of running text under a
      unit/chapter splits into individual topics.
    """

    exam_code: str
    exam_name: str
    subject_pattern: re.Pattern[str]
    unit_pattern: re.Pattern[str]
    chapter_pattern: re.Pattern[str] | None = None
    topic_split_pattern: re.Pattern[str] = re.compile(r"[;\n]")
    min_line_length: int = 2


# Default config for the NTA NEET (UG) syllabus: subjects (Physics/Chemistry/
# Botany/Zoology) are standalone header lines, each followed by "Unit I:",
# "Unit II:", ... blocks with a semicolon-separated topic list and no
# distinct Chapter level in the source document.
NEET_CONFIG = SyllabusParseConfig(
    exam_code="NEET",
    exam_name="NEET (National Eligibility cum Entrance Test)",
    subject_pattern=re.compile(r"^(PHYSICS|CHEMISTRY|BOTANY|ZOOLOGY|BIOLOGY)\s*$", re.IGNORECASE),
    unit_pattern=re.compile(r"^UNIT[\s\-]+([IVXLC]+|\d+)\s*[:\-]?\s*(.*)$", re.IGNORECASE),
)


# Boilerplate injected by government e-office/DMS systems on every page
# (file numbers, "Generated from eOffice by ..." stamps, attachment tags,
# bare page numbers). Not specific to any one exam's syllabus content, so
# it's filtered generically rather than via a per-exam config.
_NOISE_LINE_PATTERNS = (
    re.compile(r"^file\s*no\.?\s", re.IGNORECASE),
    re.compile(r"generated from eoffice", re.IGNORECASE),
    re.compile(r"^dfa/\d+", re.IGNORECASE),
    re.compile(r"^\d+/\d+/[a-z0-9]", re.IGNORECASE),
    re.compile(r"^\(computer no\.?\s*\d+\)", re.IGNORECASE),
    re.compile(r"^\d+$"),
)


def _is_noise(line: str) -> bool:
    return any(pattern.search(line) for pattern in _NOISE_LINE_PATTERNS)


def _lines(pdf_path: Path) -> list[str]:
    doc = fitz.open(pdf_path)
    try:
        lines: list[str] = []
        for page in doc:
            for raw in page.get_text("text").splitlines():
                text = raw.strip()
                if text and not _is_noise(text):
                    lines.append(text)
        return lines
    finally:
        doc.close()


class SyllabusPdfParser:
    @staticmethod
    def parse(pdf_path: str | Path, config: SyllabusParseConfig) -> list[ParsedSubject]:
        subjects: list[ParsedSubject] = []
        current_subject: ParsedSubject | None = None
        current_unit: ParsedUnit | None = None
        current_chapter: ParsedChapter | None = None

        for line in _lines(Path(pdf_path)):
            if len(line) < config.min_line_length:
                continue

            if config.subject_pattern.match(line):
                current_subject = ParsedSubject(title=line.title())
                subjects.append(current_subject)
                current_unit = None
                current_chapter = None
                continue

            unit_match = config.unit_pattern.match(line)
            if unit_match:
                if current_subject is None:
                    # No explicit subject headers in this document (single-subject
                    # syllabus) — still need a subject to hang units off of.
                    current_subject = ParsedSubject(title=config.exam_name)
                    subjects.append(current_subject)
                title = unit_match.group(2).strip() or line
                current_unit = ParsedUnit(title=title)
                current_subject.units.append(current_unit)
                current_chapter = ParsedChapter(title=current_unit.title)
                current_unit.chapters.append(current_chapter)
                continue

            if config.chapter_pattern and current_unit is not None:
                chapter_match = config.chapter_pattern.match(line)
                if chapter_match:
                    title = chapter_match.group(1).strip() or line
                    current_chapter = ParsedChapter(title=title)
                    current_unit.chapters.append(current_chapter)
                    continue

            if current_chapter is None:
                continue  # cover page / notes before the first header — skip

            for piece in config.topic_split_pattern.split(line):
                topic_title = piece.strip(" .;\t")
                if len(topic_title) >= config.min_line_length:
                    current_chapter.topics.append(ParsedTopic(title=topic_title))

        return subjects
