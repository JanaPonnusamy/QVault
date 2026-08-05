import csv
import io
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core import worker
from app.integrations.ocr import OCR
from app.integrations.video_providers import get_provider
from app.models.extraction import ExtractionJob, Frame, Question
from app.repositories.extraction_repository import ExtractionRepository
from app.services.frame_extraction_service import ExtractionOptions

#: Used only for the pre-processing estimate when a source's real frame rate
#: can't be probed (e.g. some Instagram posts don't expose fps in metadata).
_ASSUMED_FPS_WHEN_UNKNOWN = 30.0


class ExtractionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ExtractionRepository(db)

    def estimate_frames(self, url: str, source: str, sampling_fps: float | None) -> dict:
        """Frame-count estimate shown before processing: duration (probed, no
        download) x effective sampling rate. Advisory only -- actual extraction
        may keep fewer frames once the selected strategy and filters run."""
        provider = get_provider(source)
        probe = getattr(provider, "probe", None)
        meta = probe(url) if probe else {}
        duration = meta.get("duration") or 0.0
        effective_fps = sampling_fps or meta.get("fps") or _ASSUMED_FPS_WHEN_UNKNOWN
        return {
            "duration": duration,
            "fps": effective_fps,
            "estimated_frames": max(0, round(duration * effective_fps)),
        }

    def create_job(
        self,
        url: str,
        user_id: int | None,
        source: str = "youtube",
        extraction_options: ExtractionOptions | None = None,
    ) -> ExtractionJob:
        options = extraction_options or ExtractionOptions()
        job = ExtractionJob(
            url=url.strip(),
            source=source,
            status="pending",
            stage="Queued",
            created_by=user_id,
            extraction_strategy=options.strategy,
            extraction_options=options.options_json(),
        )
        self.repo.add_job(job)
        worker.submit_job(job.id)
        return job

    def create_queue(
        self,
        source_url: str,
        user_id: int | None,
        source: str,
        limit: int,
        extraction_options: ExtractionOptions | None = None,
    ) -> list[ExtractionJob]:
        """Auto-queue several acquisitions from one hashtag/profile URL --
        lists the reel/post URLs (no download yet) then hands each one to
        `create_job`, so every downstream stage (worker, extraction, OCR,
        classification) is unchanged; this only replaces pasting URLs one at a
        time."""
        from app.integrations.ytdlp import InstagramQueue

        urls = InstagramQueue.list_urls(source_url, limit)
        return [self.create_job(url, user_id, source=source, extraction_options=extraction_options) for url in urls]

    def create_upload_job(
        self,
        filename: str,
        data: bytes,
        user_id: int | None,
        source: str = "instagram",
        extraction_options: ExtractionOptions | None = None,
    ) -> ExtractionJob:
        """Create a job from a locally uploaded video (drag & drop). The file is
        saved into the job directory and the worker skips the download stage
        (``upload://`` URL scheme), reusing the full frame-extraction pipeline."""
        options = extraction_options or ExtractionOptions()
        safe_name = Path(filename).name or "video.mp4"
        job = ExtractionJob(
            url=f"upload://{safe_name}",
            source=source,
            status="pending",
            stage="Queued",
            created_by=user_id,
            title=safe_name,
            extraction_strategy=options.strategy,
            extraction_options=options.options_json(),
        )
        self.repo.add_job(job)  # commits and assigns id
        job_dir = settings.jobs_dir / str(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(safe_name).suffix.lower() or ".mp4"
        (job_dir / f"video{ext}").write_bytes(data)
        worker.submit_job(job.id)
        return job

    def get_job(self, job_id: int) -> ExtractionJob | None:
        return self.repo.get_job(job_id)

    def list_jobs(self, source: str | None = None) -> list[ExtractionJob]:
        return self.repo.list_jobs(source)

    def delete_job(self, job: ExtractionJob) -> None:
        job_dir = settings.jobs_dir / str(job.id)
        self.repo.delete_job(job)
        if job_dir.is_dir():
            shutil.rmtree(job_dir, ignore_errors=True)

    def delete_all_jobs(self, source: str) -> int:
        """Wipe every job for a source -- DB rows (frames/questions cascade)
        and their on-disk video/frame files -- for a full reset."""
        jobs = self.repo.list_jobs(source)
        for job in jobs:
            self.delete_job(job)
        return len(jobs)

    def list_frames(self, job_id: int) -> list[Frame]:
        return self.repo.list_frames(job_id)

    def frame_path(self, frame: Frame) -> Path:
        return settings.jobs_dir / str(frame.job_id) / "frames" / frame.filename

    def run_ocr(self, frame: Frame) -> Question:
        text = OCR.read_image(str(self.frame_path(frame)))
        question = Question(
            job_id=frame.job_id,
            frame_id=frame.id,
            text=text,
            timestamp=frame.timestamp,
        )
        return self.repo.add_question(question)

    def list_questions(self, job_id: int) -> list[Question]:
        return self.repo.list_questions(job_id)

    def update_question(
        self,
        question: Question,
        text: str | None = None,
        options: list[str] | None = None,
        status: str | None = None,
    ) -> Question:
        if text is not None:
            question.text = text
        if options is not None:
            question.options = json.dumps(options)
        if status is not None:
            question.status = status
        self.repo.save()
        self.db.refresh(question)
        return question

    def delete_question(self, question: Question) -> None:
        self.repo.delete_question(question)

    def _rows(self, job: ExtractionJob) -> list[dict]:
        rows = []
        for q in self.repo.list_questions(job.id):
            try:
                options = json.loads(q.options) if q.options else []
            except json.JSONDecodeError:
                options = []
            rows.append(
                {
                    "id": q.id,
                    "text": q.text,
                    "options": options,
                    "timestamp": q.timestamp,
                    "source": q.source,
                    "status": q.status,
                    "frame_start": q.frame_start,
                    "frame_end": q.frame_end,
                    "ocr_confidence": q.ocr_confidence,
                    "frame_confidence": q.frame_confidence,
                    "merge_confidence": q.merge_confidence,
                    "overall_confidence": q.overall_confidence,
                }
            )
        return rows

    def _frame_rows(self, job: ExtractionJob) -> list[dict]:
        rows = []
        for f in self.repo.list_frames(job.id):
            try:
                tags = json.loads(f.classification) if f.classification else []
            except json.JSONDecodeError:
                tags = []
            rows.append(
                {
                    "index": f.index,
                    "timestamp": f.timestamp,
                    "ocr_text": f.ocr_text,
                    "ocr_confidence": f.ocr_confidence,
                    "classification": tags,
                    "is_duplicate": f.is_duplicate,
                }
            )
        return rows

    def export(self, job: ExtractionJob, include_frames: bool = False) -> dict:
        rows = self._rows(job)
        payload = {
            "source": {
                "type": job.source,
                "url": job.url,
                "title": job.title,
                "video_id": job.video_id,
                "duration": job.duration,
                "caption": job.caption,
                "author": job.author,
                "upload_date": job.upload_date,
            },
            "question_count": len(rows),
            "questions": rows,
        }
        if include_frames:
            payload["frames"] = self._frame_rows(job)
        return payload

    def export_csv(self, job: ExtractionJob) -> str:
        rows = self._rows(job)
        buffer = io.StringIO()
        fields = [
            "id", "text", "options", "timestamp", "source", "status",
            "frame_start", "frame_end", "ocr_confidence", "frame_confidence",
            "merge_confidence", "overall_confidence",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            record = dict(row)
            record["options"] = " | ".join(row["options"])
            writer.writerow(record)
        return buffer.getvalue()

    def export_sqlite(self, job: ExtractionJob) -> Path:
        rows = self._rows(job)
        tmp = Path(tempfile.gettempdir()) / f"qvault_questions_job_{job.id}.sqlite"
        if tmp.exists():
            tmp.unlink()
        conn = sqlite3.connect(tmp)
        conn.execute(
            """
            CREATE TABLE questions (
                id INTEGER, job_id INTEGER, text TEXT, options TEXT,
                timestamp REAL, source TEXT, status TEXT,
                frame_start INTEGER, frame_end INTEGER,
                ocr_confidence REAL, frame_confidence REAL,
                merge_confidence REAL, overall_confidence REAL
            )
            """
        )
        conn.executemany(
            "INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    r["id"], job.id, r["text"], json.dumps(r["options"]),
                    r["timestamp"], r["source"], r["status"],
                    r["frame_start"], r["frame_end"], r["ocr_confidence"],
                    r["frame_confidence"], r["merge_confidence"], r["overall_confidence"],
                )
                for r in rows
            ],
        )
        conn.commit()
        conn.close()
        return tmp
