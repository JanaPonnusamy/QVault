from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.extraction import ExtractionJob, Frame, Question


class ExtractionRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- jobs ---
    def get_job(self, job_id: int) -> ExtractionJob | None:
        return self.db.get(ExtractionJob, job_id)

    def list_jobs(self) -> list[ExtractionJob]:
        return list(self.db.scalars(select(ExtractionJob).order_by(ExtractionJob.id.desc())))

    def add_job(self, job: ExtractionJob) -> ExtractionJob:
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def save(self) -> None:
        self.db.commit()

    def delete_job(self, job: ExtractionJob) -> None:
        self.db.delete(job)
        self.db.commit()

    # --- frames ---
    def get_frame(self, frame_id: int) -> Frame | None:
        return self.db.get(Frame, frame_id)

    def list_frames(self, job_id: int) -> list[Frame]:
        return list(
            self.db.scalars(select(Frame).where(Frame.job_id == job_id).order_by(Frame.index))
        )

    def add_frames(self, frames: list[Frame]) -> None:
        self.db.add_all(frames)
        self.db.commit()

    # --- questions ---
    def get_question(self, question_id: int) -> Question | None:
        return self.db.get(Question, question_id)

    def list_questions(self, job_id: int) -> list[Question]:
        return list(
            self.db.scalars(select(Question).where(Question.job_id == job_id).order_by(Question.id))
        )

    def add_question(self, question: Question) -> Question:
        self.db.add(question)
        self.db.commit()
        self.db.refresh(question)
        return question

    def delete_question(self, question: Question) -> None:
        self.db.delete(question)
        self.db.commit()
