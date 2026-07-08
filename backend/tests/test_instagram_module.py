"""Tests for the Instagram Acquisition module.

Deterministic and offline: the content classifier is pure, and the service/repo
tests run against an isolated in-memory SQLite engine with pre-OCR'd frames, so
no network / FFmpeg / OCR is exercised.
"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.models.extraction import ExtractionJob, Frame
from app.services.classification_service import ClassificationService, classify


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    db = Session()
    try:
        yield db
    finally:
        db.close()


# ---------- classifier ----------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("Q1. What is the capital of France?\n(A) Paris\n(B) Rome", {"question", "options"}),
        ("Which of the following is a noble gas?\n1) Oxygen\n2) Neon", {"question", "options"}),
        ("Answer: (B) Neon", {"answer"}),
        ("THE FRENCH REVOLUTION", {"heading"}),
        ("Figure 2.1 The water cycle", {"diagram"}),
        ("Name    Age    City\nAsha    12    Pune\nRavi    13    Delhi", {"table"}),
        (
            "Photosynthesis is the process by which green plants convert light "
            "energy into chemical energy stored in glucose.",
            {"paragraph"},
        ),
        ("", set()),
        ("   \n  ", set()),
    ],
)
def test_classify(text, expected):
    assert set(classify(text)) == expected


def test_classify_is_ordered_and_stable():
    tags = classify("Q. Pick one?\n(A) x\n(B) y")
    assert tags == sorted(tags, key=lambda t: ["heading", "paragraph", "question", "options", "answer", "diagram", "table"].index(t))


# ---------- source isolation ----------

def test_list_jobs_filters_by_source(session):
    from app.repositories.extraction_repository import ExtractionRepository

    session.add(ExtractionJob(url="https://youtu.be/x", source="youtube"))
    session.add(ExtractionJob(url="https://instagram.com/reel/y", source="instagram"))
    session.commit()

    repo = ExtractionRepository(session)
    assert {j.source for j in repo.list_jobs("instagram")} == {"instagram"}
    assert {j.source for j in repo.list_jobs("youtube")} == {"youtube"}
    assert len(repo.list_jobs()) == 2


def test_default_source_is_youtube(session):
    job = ExtractionJob(url="https://youtu.be/x")
    session.add(job)
    session.commit()
    assert job.source == "youtube"


# ---------- classification service ----------

def test_process_job_classifies_pre_ocrd_frames(session):
    job = ExtractionJob(url="https://instagram.com/reel/z", source="instagram")
    session.add(job)
    session.commit()

    frames = [
        Frame(job_id=job.id, index=0, filename="frame_00001.jpg",
              ocr_text="THE CELL", ocr_done=True),
        Frame(job_id=job.id, index=1, filename="frame_00002.jpg",
              ocr_text="Q1. Which organelle is the powerhouse?\n(A) Nucleus\n(B) Mitochondria",
              ocr_done=True),
        Frame(job_id=job.id, index=2, filename="frame_00003.jpg",
              ocr_text="duplicate", ocr_done=True, is_duplicate=True),
    ]
    session.add_all(frames)
    session.commit()

    result = ClassificationService(session).process_job(job.id)

    # Duplicate frame is skipped.
    assert result == {"frames": 2, "classified": 2}
    heading = session.get(Frame, frames[0].id)
    question = session.get(Frame, frames[1].id)
    assert json.loads(heading.classification) == ["heading"]
    assert set(json.loads(question.classification)) == {"question", "options"}


def test_process_job_missing_job_is_safe(session):
    assert ClassificationService(session).process_job(9999) == {"frames": 0, "classified": 0}


# ---------- routing / RBAC wiring ----------

def test_instagram_routes_registered():
    from app.api.routers import instagram

    paths = {r.path for r in instagram.router.routes}
    assert "/api/sources/instagram/jobs" in paths
    assert "/api/sources/instagram/jobs/{job_id}/analyze" in paths
    assert "/api/sources/instagram/jobs/{job_id}/export" in paths


def test_instagram_permissions_seeded():
    from app.core.seed import MODULE_ACTIONS

    assert MODULE_ACTIONS["instagram"] == ["view", "create", "update", "delete", "execute", "export"]
