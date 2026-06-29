import json
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.integrations.frame_analysis import FrameAnalyzer
from app.integrations.ocr import OCR
from app.models.extraction import ExtractionJob, Frame, Question

OPTION_RE = re.compile(r"^\s*(\(?[A-Da-d][\).]|[1-4][\).])\s+\S")


def _frame_path(job_id: int, filename: str) -> Path:
    return settings.jobs_dir / str(job_id) / "frames" / filename


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _line_set(text: str) -> set[str]:
    return {ln.lower() for ln in _lines(text)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _split_stem_options(lines: list[str]) -> tuple[str, list[str]]:
    stem: list[str] = []
    options: list[str] = []
    for line in lines:
        if OPTION_RE.match(line):
            options.append(line)
        else:
            stem.append(line)
    return "\n".join(stem).strip(), options


class AnalysisService:
    """Sprint 2 automation: dedup, question detection, auto-OCR, merge."""

    def __init__(self, db: Session):
        self.db = db

    def analyze_job(self, job_id: int) -> dict:
        job = self.db.get(ExtractionJob, job_id)
        if not job:
            return {}

        frames = list(
            self.db.scalars(select(Frame).where(Frame.job_id == job_id).order_by(Frame.index))
        )

        self._score_and_dedup(job_id, frames)
        question_frames = [f for f in frames if f.is_question and not f.is_duplicate]
        self._auto_ocr(job_id, question_frames)
        merged = self._merge_questions(job, question_frames)

        self.db.commit()
        return {
            "frames_total": len(frames),
            "frames_unique": sum(1 for f in frames if not f.is_duplicate),
            "frames_question": len(question_frames),
            "questions_created": merged,
        }

    def _score_and_dedup(self, job_id: int, frames: list[Frame]) -> None:
        threshold = settings.question_threshold
        last_kept_sig = None
        for frame in frames:
            path = str(_frame_path(job_id, frame.filename))
            frame.question_score = FrameAnalyzer.question_probability(path)
            frame.is_question = frame.question_score >= threshold
            frame.phash = FrameAnalyzer.dhash(path)

            signature = FrameAnalyzer.signature(path)
            if last_kept_sig is not None and (
                FrameAnalyzer.difference(signature, last_kept_sig) <= settings.dedup_mad
            ):
                frame.is_duplicate = True
            else:
                frame.is_duplicate = False
                last_kept_sig = signature
        self.db.commit()

    def _auto_ocr(self, job_id: int, question_frames: list[Frame]) -> None:
        for frame in question_frames:
            if frame.ocr_done:
                continue
            text, confidence = OCR.read_image_detailed(str(_frame_path(job_id, frame.filename)))
            frame.ocr_text = text
            frame.ocr_confidence = confidence
            frame.ocr_done = True
        self.db.commit()

    def _merge_questions(self, job: ExtractionJob, question_frames: list[Frame]) -> int:
        # Replace previous auto-generated questions; keep manual ones untouched.
        for old in self.db.scalars(
            select(Question).where(Question.job_id == job.id, Question.source == "auto")
        ):
            self.db.delete(old)
        self.db.commit()

        usable = [f for f in question_frames if f.ocr_text.strip()]
        if not usable:
            return 0

        groups: list[list[Frame]] = []
        sims: list[list[float]] = []
        current: list[Frame] = [usable[0]]
        current_sims: list[float] = []

        for prev, frame in zip(usable, usable[1:]):
            sim = _jaccard(_line_set(prev.ocr_text), _line_set(frame.ocr_text))
            prev_set, cur_set = _line_set(prev.ocr_text), _line_set(frame.ocr_text)
            subset = prev_set <= cur_set or cur_set <= prev_set
            if sim >= settings.merge_threshold or subset:
                current.append(frame)
                current_sims.append(sim)
            else:
                groups.append(current)
                sims.append(current_sims)
                current = [frame]
                current_sims = []
        groups.append(current)
        sims.append(current_sims)

        for group, group_sims in zip(groups, sims):
            self.db.add(self._build_question(job.id, group, group_sims))
        self.db.commit()
        return len(groups)

    def _build_question(self, job_id: int, group: list[Frame], group_sims: list[float]) -> Question:
        merged_lines: list[str] = []
        seen: set[str] = set()
        for frame in group:
            for line in _lines(frame.ocr_text):
                key = line.lower()
                if key not in seen:
                    seen.add(key)
                    merged_lines.append(line)

        stem, options = _split_stem_options(merged_lines)

        ocr_conf = sum(f.ocr_confidence for f in group) / len(group)
        frame_conf = sum(f.question_score for f in group) / len(group)
        merge_conf = 1.0 if len(group) == 1 else sum(group_sims) / len(group_sims)
        overall = round(0.5 * ocr_conf + 0.3 * frame_conf + 0.2 * merge_conf, 4)

        return Question(
            job_id=job_id,
            frame_id=group[0].id,
            frame_start=group[0].index,
            frame_end=group[-1].index,
            timestamp=group[0].timestamp,
            text=stem or "\n".join(merged_lines),
            options=json.dumps(options),
            source="auto",
            status="pending",
            ocr_confidence=round(ocr_conf, 4),
            frame_confidence=round(frame_conf, 4),
            merge_confidence=round(merge_conf, 4),
            overall_confidence=overall,
        )
