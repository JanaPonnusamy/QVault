"""Frame Sampling Mode tests.

Covers the new pipeline stage inserted ahead of strategy selection:
    Video -> Frame Sampling -> Selected Strategy -> OCR -> Classification -> Questions

The core claim under test: sampling at a coarse fps (the 10 FPS default) can
miss sub-300ms flash content, while "every decoded frame" sampling (fps=None)
catches it. Built with a real synthetic MP4 containing a single ~33ms flash
frame -- ground truth is exact because we authored the video.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.config.settings import settings
from app.integrations.ffmpeg import FFmpeg
from app.services.extraction_service import ExtractionService
from app.services.frame_extraction_service import (
    DEFAULT_SAMPLING_FPS,
    SAMPLING_FPS_OPTIONS,
    ExtractionOptions,
    HybridStrategy,
    OCRTextChangeStrategy,
)

from video_fixtures import make_color_video

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def flash_frame_video(tmp_path_factory):
    """3s @ 30fps white video with a single ~33ms red 'FLASH' frame at t=1.5s --
    one native frame wide, well under any of the coarser sampling intervals.
    Used for OCRTextChangeStrategy, whose keep/skip decision is pure OCR-text
    diff (no scene-magnitude threshold involved)."""
    import subprocess

    path = tmp_path_factory.mktemp("flash").parent / "flash_frame_video.mp4"
    subprocess.run(
        [
            settings.ffmpeg_path, "-y",
            "-f", "lavfi", "-i", "color=c=white:size=320x240:duration=3:rate=30",
            "-vf", "drawtext=text='FLASH':fontcolor=red:fontsize=30:x=10:y=10:enable='between(t,1.5,1.533)'",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return path


@pytest.fixture(scope="module")
def flash_color_video(tmp_path_factory):
    """3s @ 30fps white video with a single ~33ms full-frame red flash at
    t=1.5s (a camera-flash/screen-flash scenario) -- large enough a visual
    change to register with Hybrid's scene-detection stage, unlike a small
    text overlay on an otherwise unchanged background."""
    path = tmp_path_factory.mktemp("flash_color").parent / "flash_color_video.mp4"
    make_color_video(path, [("white", 1.5), ("red", 1 / 30), ("white", 1.5 - 1 / 30)], rate=30)
    return path


def _contains_flash_text(frames_dir, frames) -> bool:
    from app.integrations.ocr import OCR

    for name, _ in frames:
        text, _ = OCR.read_image_detailed(str(frames_dir / name))
        if "FLASH" in text.upper():
            return True
    return False


# ---------- FFmpeg.extract_frames_sampled ----------

class TestExtractFramesSampled:
    def test_every_frame_mode_yields_native_frame_count(self, flash_frame_video, tmp_path):
        frames = FFmpeg.extract_frames_sampled(str(flash_frame_video), tmp_path / "every", fps=None)
        assert len(frames) == 90  # 3s @ 30fps, exactly

    def test_fps_limited_mode_yields_fewer_candidates(self, flash_frame_video, tmp_path):
        frames = FFmpeg.extract_frames_sampled(str(flash_frame_video), tmp_path / "fps10", fps=10.0)
        assert len(frames) == pytest.approx(30, abs=2)


# ---------- Flash-frame detection: the actual bug this feature fixes ----------

class TestFlashFrameDetection:
    def test_default_10fps_sampling_misses_the_flash(self, flash_frame_video, tmp_path):
        frames = OCRTextChangeStrategy().extract(
            str(flash_frame_video), tmp_path / "ocr_10fps", ExtractionOptions(sampling_fps=10.0), 3.0
        )
        assert not _contains_flash_text(tmp_path / "ocr_10fps", frames)

    def test_every_frame_sampling_catches_the_flash(self, flash_frame_video, tmp_path):
        frames = OCRTextChangeStrategy().extract(
            str(flash_frame_video), tmp_path / "ocr_every", ExtractionOptions(sampling_fps=None), 3.0
        )
        assert _contains_flash_text(tmp_path / "ocr_every", frames)

    def test_hybrid_with_every_frame_sampling_catches_the_flash(self, flash_color_video, tmp_path):
        """Matches the spec's own example: Sampling=Every Frame, Strategy=Hybrid
        -> detect a 100-300ms flash frame (here a full-frame color flash, a
        realistic camera/screen-flash scenario with enough visual magnitude to
        register with scene detection -- a small text overlay may not)."""
        frames = HybridStrategy().extract(
            str(flash_color_video), tmp_path / "hybrid_every", ExtractionOptions(sampling_fps=None), 3.0
        )
        assert len(frames) >= 2  # opening frame + the flash

    def test_hybrid_with_default_10fps_misses_the_flash(self, flash_color_video, tmp_path):
        frames = HybridStrategy().extract(
            str(flash_color_video), tmp_path / "hybrid_10fps", ExtractionOptions(sampling_fps=10.0), 3.0
        )
        assert len(frames) == 1  # only the opening frame -- the flash fell between samples


# ---------- ExtractionOptions sampling_fps ----------

class TestSamplingFpsOptions:
    def test_default_is_10fps(self):
        assert ExtractionOptions().sampling_fps == DEFAULT_SAMPLING_FPS == 10.0

    def test_all_ui_offered_modes_present(self):
        assert SAMPLING_FPS_OPTIONS == (None, 30.0, 15.0, 10.0, 5.0, 2.0, 1.0)

    def test_options_json_roundtrips_every_frame_mode(self):
        opts = ExtractionOptions(sampling_fps=None)
        raw = opts.options_json()
        assert json.loads(raw)["sampling_fps"] is None

        class FakeJob:
            extraction_strategy = "hybrid"
            extraction_options = raw

        assert ExtractionOptions.from_job(FakeJob()).sampling_fps is None


# ---------- Frame-count estimate ----------

class _FakeProvider:
    def __init__(self, duration=10.0, fps=30.0):
        self._duration = duration
        self._fps = fps

    def probe(self, ref):
        return {"duration": self._duration, "fps": self._fps}


class _FakeProviderWithoutProbe:
    """No `probe` method at all -- exercises the graceful-fallback path for
    providers that don't support the estimate feature."""


class TestEstimateFrames:
    def test_explicit_sampling_fps_drives_estimate(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.extraction_service.get_provider", lambda source: _FakeProvider(duration=10.0, fps=30.0)
        )
        result = ExtractionService(db=None).estimate_frames("http://x", "youtube", sampling_fps=10.0)
        assert result["duration"] == 10.0
        assert result["fps"] == 10.0
        assert result["estimated_frames"] == 100

    def test_every_frame_mode_uses_probed_source_fps(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.extraction_service.get_provider", lambda source: _FakeProvider(duration=10.0, fps=24.0)
        )
        result = ExtractionService(db=None).estimate_frames("http://x", "youtube", sampling_fps=None)
        assert result["fps"] == 24.0
        assert result["estimated_frames"] == 240

    def test_every_frame_mode_falls_back_when_source_fps_unknown(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.extraction_service.get_provider", lambda source: _FakeProvider(duration=10.0, fps=0.0)
        )
        result = ExtractionService(db=None).estimate_frames("http://x", "youtube", sampling_fps=None)
        assert result["fps"] == 30.0  # documented fallback assumption
        assert result["estimated_frames"] == 300

    def test_provider_without_probe_support_returns_zeroed_advisory_result(self, monkeypatch):
        provider = _FakeProviderWithoutProbe()
        monkeypatch.setattr("app.services.extraction_service.get_provider", lambda source: provider)
        result = ExtractionService(db=None).estimate_frames("http://x", "youtube", sampling_fps=10.0)
        assert result["duration"] == 0.0
        assert result["estimated_frames"] == 0


# ---------- Estimate API endpoints ----------

class TestEstimateEndpoint:
    def test_youtube_estimate_endpoint(self, monkeypatch):
        from app.core.app import app as real_app

        monkeypatch.setattr(
            "app.services.extraction_service.get_provider", lambda source: _FakeProvider(duration=20.0, fps=30.0)
        )
        client = TestClient(real_app)
        token = client.post(
            "/api/auth/login", data={"username": settings.admin_username, "password": settings.admin_password}
        ).json()["access_token"]

        res = client.post(
            "/api/extractor/estimate",
            json={"url": "https://youtu.be/x", "sampling_fps": 10.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["estimated_frames"] == 200
        assert body["duration"] == 20.0

    def test_instagram_estimate_endpoint(self, monkeypatch):
        from app.core.app import app as real_app

        monkeypatch.setattr(
            "app.services.extraction_service.get_provider", lambda source: _FakeProvider(duration=6.0, fps=30.0)
        )
        client = TestClient(real_app)
        token = client.post(
            "/api/auth/login", data={"username": settings.admin_username, "password": settings.admin_password}
        ).json()["access_token"]

        res = client.post(
            "/api/sources/instagram/estimate",
            json={"url": "https://instagram.com/reel/x", "sampling_fps": None},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json()["estimated_frames"] == 180

    def test_estimate_rejects_invalid_sampling_fps(self, monkeypatch):
        from app.core.app import app as real_app

        client = TestClient(real_app)
        token = client.post(
            "/api/auth/login", data={"username": settings.admin_username, "password": settings.admin_password}
        ).json()["access_token"]

        res = client.post(
            "/api/extractor/estimate",
            json={"url": "https://youtu.be/x", "sampling_fps": 7.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422
