"""End-to-end proof: the Frame Extraction Engine works through the *real*
acquisition pipeline (job row -> worker -> provider -> strategy -> Frame rows)
for a local MP4 -- not just the extraction service in isolation.

Registers a throwaway `VideoProvider` whose `fetch()` copies a local file
instead of downloading a URL (exactly the extension point
`integrations/video_providers.py` was built for). This is not wired into any
router/UI -- it exists only to drive `core.worker._run_job` synchronously
against the real database for this test, then cleans up after itself.
"""
import shutil

import pytest

from app.config.settings import settings
from app.database.session import SessionLocal
from app.integrations import video_providers
from app.models.extraction import ExtractionJob, Frame
from app.services.frame_extraction_service import STRATEGIES

from video_fixtures import make_color_text_video

pytestmark = pytest.mark.slow


class _LocalFileProvider:
    name = "local_test_mp4"
    classify_frames = False

    def fetch(self, ref: str, output_dir: object) -> dict:
        from pathlib import Path

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        dest = output_dir / "video.mp4"
        shutil.copyfile(ref, dest)
        return {
            "title": "Local MP4 test video",
            "video_id": "local-test",
            "duration": 6,
            "path": str(dest),
            "caption": "",
            "author": "",
            "upload_date": "",
            "thumbnail": "",
            "meta": {},
        }


@pytest.fixture(scope="module")
def local_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("local_mp4") / "source.mp4"
    make_color_text_video(path, [("red", "ALPHA", 2), ("blue", "BETA", 2), ("green", "GAMMA", 2)])
    return path


@pytest.fixture(autouse=True, scope="module")
def _register_local_provider():
    video_providers.register(_LocalFileProvider())
    yield
    video_providers._PROVIDERS.pop("local_test_mp4", None)


@pytest.fixture()
def db():
    session = SessionLocal()
    created_job_ids: list[int] = []
    try:
        yield session, created_job_ids
    finally:
        for job_id in created_job_ids:
            shutil.rmtree(settings.jobs_dir / str(job_id), ignore_errors=True)
            stored = session.get(ExtractionJob, job_id)
            if stored:
                session.delete(stored)
        session.commit()
        session.close()


def _run_job_for(db, created_job_ids, local_video, strategy: str) -> ExtractionJob:
    from app.core.worker import _run_job

    job = ExtractionJob(
        url=str(local_video),
        source="local_test_mp4",
        status="pending",
        stage="Queued",
        extraction_strategy=strategy,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    created_job_ids.append(job.id)

    _run_job(job.id)  # synchronous call -- no thread pool, deterministic for the test
    db.expire_all()
    return db.get(ExtractionJob, job.id)


@pytest.mark.parametrize("strategy", list(STRATEGIES))
def test_local_mp4_runs_through_real_worker_for_every_strategy(db, local_video, strategy):
    session, created_job_ids = db
    job = _run_job_for(session, created_job_ids, local_video, strategy)
    assert job.status == "ready", job.error
    assert job.frame_count >= 1
    assert job.extraction_strategy == strategy

    frames = list(session.query(Frame).filter(Frame.job_id == job.id))
    assert len(frames) == job.frame_count
    for frame in frames:
        path = settings.jobs_dir / str(job.id) / "frames" / frame.filename
        assert path.is_file()


def test_local_mp4_hybrid_produces_fewer_frames_than_fine_fixed_interval(db, local_video):
    """Sanity check on the original complaint's inverse: Hybrid should not
    produce more raw frames than a fine fixed interval on the same clip --
    it's trading blanket sampling for meaningful-change selection."""
    session, created_job_ids = db
    hybrid_job = _run_job_for(session, created_job_ids, local_video, "hybrid")
    fixed_job = _run_job_for(session, created_job_ids, local_video, "fixed_interval")
    assert hybrid_job.frame_count <= fixed_job.frame_count
