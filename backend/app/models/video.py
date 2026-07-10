from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Video(Base):
    """A generated educational video (landscape video, short or reel).

    Render jobs run through the generic ``acquisition_jobs`` table
    (``job_type="video_render"``); this row is the durable output registry.
    """

    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20), default="video", index=True)  # video|short|reel
    orientation: Mapped[str] = mapped_column(String(20), default="landscape")
    width: Mapped[int] = mapped_column(Integer, default=1920)
    height: Mapped[int] = mapped_column(Integer, default=1080)
    fps: Mapped[int] = mapped_column(Integer, default=30)
    duration: Mapped[float] = mapped_column(Float, default=0.0)

    category: Mapped[str] = mapped_column(String(160), default="General Knowledge")
    source_file: Mapped[str] = mapped_column(String(500), default="")
    topic: Mapped[str] = mapped_column(String(200), default="", index=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    question_ids: Mapped[str] = mapped_column(Text, default="")  # JSON list

    template: Mapped[str] = mapped_column(String(60), default="glass_dark")
    tts_provider: Mapped[str] = mapped_column(String(40), default="edge")
    tts_voice: Mapped[str] = mapped_column(String(80), default="")

    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(500), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    srt_path: Mapped[str] = mapped_column(String(500), default="")
    thumbnail_path: Mapped[str] = mapped_column(String(500), default="")

    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
