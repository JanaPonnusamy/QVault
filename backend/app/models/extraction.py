from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(300), default="")
    video_id: Mapped[str] = mapped_column(String(40), default="")
    duration: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    stage: Mapped[str] = mapped_column(String(60), default="")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    frame_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    frames: Mapped[list["Frame"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Frame.index"
    )
    questions: Mapped[list["Question"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Question.id"
    )


class Frame(Base):
    __tablename__ = "frames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("extraction_jobs.id", ondelete="CASCADE"), index=True)
    index: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[float] = mapped_column(Float, default=0.0)
    filename: Mapped[str] = mapped_column(String(255))

    question_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_question: Mapped[bool] = mapped_column(Boolean, default=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    phash: Mapped[str] = mapped_column(String(64), default="")
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    ocr_done: Mapped[bool] = mapped_column(Boolean, default=False)

    job: Mapped[ExtractionJob] = relationship(back_populates="frames")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("extraction_jobs.id", ondelete="CASCADE"), index=True)
    frame_id: Mapped[int | None] = mapped_column(ForeignKey("frames.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    options: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    frame_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    merge_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    frame_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    job: Mapped[ExtractionJob] = relationship(back_populates="questions")
