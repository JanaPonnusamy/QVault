"""Frame Extraction Engine (Strategy Pattern) tests.

All fixtures are synthetic local MP4s built purely from ffmpeg lavfi sources --
no network, no real media. This is a legitimate "local MP4" input: every
acquisition source (YouTube, Instagram, and any future source) downloads to a
local video.mp4 before this stage runs, and the strategies below operate on
nothing else. Timestamps/ground truth are known exactly (we built the video),
so these tests assert precise correctness, not just "it ran".
"""
import shutil
from pathlib import Path

import pytest

from app.integrations.frame_analysis import FrameAnalyzer
from app.services.frame_extraction_service import (
    STRATEGIES,
    ExtractionOptions,
    FixedIntervalStrategy,
    FrameExtractionService,
    HybridStrategy,
    OCRTextChangeStrategy,
    SceneDetectionStrategy,
    _apply_filters,
    _dedup_visual,
    _subsample,
)

from video_fixtures import make_color_text_video, make_color_video, make_text_video

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def color_cycle_video(tmp_path_factory):
    """10s video, 5 x 2s solid-color segments -- reproduces the original bug
    report exactly (a 10s Reel producing only 5 frames at a 2s fixed interval)."""
    path = tmp_path_factory.mktemp("videos") / "color_cycle.mp4"
    make_color_video(path, [("red", 2), ("blue", 2), ("green", 2), ("yellow", 2), ("purple", 2)])
    return path


@pytest.fixture(scope="module")
def three_scene_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("videos") / "three_scene.mp4"
    make_color_video(path, [("red", 2), ("blue", 2), ("green", 2)])
    return path


@pytest.fixture(scope="module")
def text_change_video(tmp_path_factory):
    """Mirrors the spec's worked example: Photosynthesis (save) -> repeats
    (skip) -> Cell Division (save) -> repeat (skip) -> DNA Replication (save)."""
    path = tmp_path_factory.mktemp("videos") / "text_change.mp4"
    make_text_video(path, [("PHOTOSYNTHESIS", 1.5), ("CELL DIVISION", 1.5), ("DNA REPLICATION", 1.5)])
    return path


@pytest.fixture(scope="module")
def scene_and_text_video(tmp_path_factory):
    """Each segment changes BOTH background color (a real scene-detection
    trigger) and text (an OCR-diff trigger), so Hybrid's two signals are both
    exercised together."""
    path = tmp_path_factory.mktemp("videos") / "scene_and_text.mp4"
    make_color_text_video(path, [("red", "ALPHA", 2), ("blue", "BETA", 2), ("green", "GAMMA", 2)])
    return path


# ---------- Strategy 1: Fixed Interval ----------

class TestFixedIntervalStrategy:
    def test_original_bug_only_five_frames_at_2s_interval(self, color_cycle_video):
        """The exact scenario from the bug report: a 10s video at the old fixed
        ~2s interval produces only 5 frames."""
        frames_dir = color_cycle_video.parent / "fixed_2s"
        frames = FixedIntervalStrategy().extract(
            str(color_cycle_video), frames_dir, ExtractionOptions(interval=2.0), 10.0
        )
        assert len(frames) == 5
        assert [ts for _, ts in frames] == [0.0, 2.0, 4.0, 6.0, 8.0]

    def test_quarter_second_interval_produces_far_more_frames(self, color_cycle_video):
        """The fix: a finer interval (0.25s) catches brief content the old fixed
        interval would skip entirely."""
        frames_dir = color_cycle_video.parent / "fixed_0.25s"
        frames = FixedIntervalStrategy().extract(
            str(color_cycle_video), frames_dir, ExtractionOptions(interval=0.25), 10.0
        )
        assert len(frames) >= 35  # ~40 expected at 0.25s over 10s
        for name, _ in frames:
            assert (frames_dir / name).is_file()

    @pytest.mark.parametrize("interval", [0.25, 0.5, 1, 2, 5])
    def test_all_ui_offered_intervals_work(self, color_cycle_video, interval):
        frames_dir = color_cycle_video.parent / f"fixed_{interval}"
        frames = FixedIntervalStrategy().extract(
            str(color_cycle_video), frames_dir, ExtractionOptions(interval=interval), 10.0
        )
        assert len(frames) >= 1
        expected_count = round(10.0 / interval)
        assert abs(len(frames) - expected_count) <= 1

    def test_auto_interval_when_none_given(self, color_cycle_video):
        frames_dir = color_cycle_video.parent / "fixed_auto"
        frames = FixedIntervalStrategy().extract(
            str(color_cycle_video), frames_dir, ExtractionOptions(interval=None, max_frames=20), 10.0
        )
        assert 1 <= len(frames) <= 21


# ---------- Strategy 2: Scene Detection ----------

class TestSceneDetectionStrategy:
    def test_detects_each_scene_boundary_plus_opening_frame(self, three_scene_video):
        frames_dir = three_scene_video.parent / "scene_only"
        frames = SceneDetectionStrategy().extract(
            str(three_scene_video), frames_dir, ExtractionOptions(scene_threshold=0.35), 6.0
        )
        timestamps = [ts for _, ts in frames]
        assert timestamps[0] == 0.0  # opening frame always included
        assert len(frames) == 3
        assert timestamps[1] == pytest.approx(2.0, abs=0.1)
        assert timestamps[2] == pytest.approx(4.0, abs=0.1)
        for name, _ in frames:
            assert (frames_dir / name).is_file()

    def test_static_video_yields_only_opening_frame(self, tmp_path):
        path = tmp_path / "static.mp4"
        make_color_video(path, [("gray", 3)])
        frames_dir = tmp_path / "scene_static"
        frames = SceneDetectionStrategy().extract(str(path), frames_dir, ExtractionOptions(), 3.0)
        assert len(frames) == 1
        assert frames[0][1] == 0.0


# ---------- Strategy 3: OCR Text Change ----------

class TestOCRTextChangeStrategy:
    def test_save_skip_matches_spec_example(self, text_change_video):
        """Photosynthesis(save)/repeat(skip)/repeat(skip) -> Cell Division(save)/
        repeat(skip) -> DNA Replication(save): exactly 3 kept frames."""
        frames_dir = text_change_video.parent / "ocr_only"
        frames = OCRTextChangeStrategy().extract(
            str(text_change_video), frames_dir, ExtractionOptions(sample_interval=0.5), 4.5
        )
        assert len(frames) == 3
        assert [ts for _, ts in frames] == [0.0, 1.5, 3.0]
        for name, _ in frames:
            assert (frames_dir / name).is_file()

    def test_scratch_sampling_dir_is_cleaned_up(self, text_change_video):
        frames_dir = text_change_video.parent / "ocr_cleanup_check"
        OCRTextChangeStrategy().extract(
            str(text_change_video), frames_dir, ExtractionOptions(sample_interval=0.5), 4.5
        )
        assert not (frames_dir / "_sample").exists()


# ---------- Strategy 4: Hybrid ----------

class TestHybridStrategy:
    def test_combined_scene_and_text_changes(self, scene_and_text_video):
        from app.integrations.ocr import OCR

        frames_dir = scene_and_text_video.parent / "hybrid_combined"
        frames = HybridStrategy().extract(
            str(scene_and_text_video), frames_dir, ExtractionOptions(scene_threshold=0.35), 6.0
        )
        assert len(frames) == 3
        texts = [OCR.read_image_detailed(str(frames_dir / name))[0] for name, _ in frames]
        assert any("ALPHA" in t for t in texts)
        assert any("BETA" in t for t in texts)
        assert any("GAMMA" in t for t in texts)

    def test_textless_scene_changes_are_not_collapsed(self, three_scene_video):
        """Regression guard: a scene change with NO OCR text on either side must
        not be treated as 'unchanged' just because both sides read empty text --
        that would silently undo scene detection's decision (camera cuts, plain
        diagram swaps have no text at all)."""
        frames_dir = three_scene_video.parent / "hybrid_no_text"
        frames = HybridStrategy().extract(
            str(three_scene_video), frames_dir, ExtractionOptions(scene_threshold=0.35), 6.0
        )
        assert len(frames) == 3

    def test_scratch_scene_dir_is_cleaned_up(self, three_scene_video):
        frames_dir = three_scene_video.parent / "hybrid_cleanup_check"
        HybridStrategy().extract(str(three_scene_video), frames_dir, ExtractionOptions(), 6.0)
        assert not (frames_dir / "_scene").exists()


# ---------- ExtractionOptions ----------

class TestExtractionOptions:
    def test_options_json_roundtrip(self):
        opts = ExtractionOptions(
            strategy="scene_detection", interval=1.0, max_frames=50, remove_duplicates=False
        )
        raw = opts.options_json()

        class FakeJob:
            extraction_strategy = "scene_detection"
            extraction_options = raw

        restored = ExtractionOptions.from_job(FakeJob())
        assert restored.strategy == "scene_detection"
        assert restored.interval == 1.0
        assert restored.max_frames == 50
        assert restored.remove_duplicates is False

    def test_from_job_falls_back_to_hybrid_on_invalid_strategy(self):
        class FakeJob:
            extraction_strategy = "not_a_real_strategy"
            extraction_options = ""

        assert ExtractionOptions.from_job(FakeJob()).strategy == "hybrid"

    def test_from_job_handles_malformed_options_json(self):
        class FakeJob:
            extraction_strategy = "hybrid"
            extraction_options = "{not json"

        opts = ExtractionOptions.from_job(FakeJob())
        assert opts.strategy == "hybrid"
        assert opts.remove_duplicates is True  # default preserved

    def test_from_payload_duck_types_any_matching_object(self):
        class FakePayload:
            strategy = "fixed_interval"
            interval = 0.5
            scene_threshold = 0.35
            sample_interval = 0.5
            max_frames = None
            remove_duplicates = True
            keep_best_quality = True
            ignore_blank = True
            ignore_blurred = True

        opts = ExtractionOptions.from_payload(FakePayload())
        assert opts.strategy == "fixed_interval"
        assert opts.interval == 0.5

    def test_all_four_strategies_are_registered(self):
        assert set(STRATEGIES) == {
            "fixed_interval", "scene_detection", "ocr_text_change", "hybrid",
        }


# ---------- FrameExtractionService dispatch ----------

class TestFrameExtractionServiceDispatch:
    @pytest.mark.parametrize("strategy", list(STRATEGIES))
    def test_dispatches_to_each_strategy_and_returns_real_files(self, three_scene_video, strategy):
        frames_dir = three_scene_video.parent / f"dispatch_{strategy}"
        opts = ExtractionOptions(strategy=strategy, remove_duplicates=False, ignore_blank=False, ignore_blurred=False)
        frames = FrameExtractionService().extract(str(three_scene_video), frames_dir, opts, 6.0)
        assert len(frames) >= 1
        for name, _ in frames:
            assert (frames_dir / name).is_file()

    def test_unknown_strategy_falls_back_to_hybrid(self, scene_and_text_video):
        # Uses a video with real texture (not solid color, so default
        # ignore_blank=True doesn't strip everything) to exercise the fallback
        # under the same default filter pipeline a real job would use.
        frames_dir = scene_and_text_video.parent / "dispatch_unknown"
        opts = ExtractionOptions(strategy="totally_unknown")
        frames = FrameExtractionService().extract(str(scene_and_text_video), frames_dir, opts, 6.0)
        assert len(frames) >= 1


# ---------- Shared quality filters (Advanced options) ----------

class TestSharedFilters:
    def _make_solid_frame(self, frames_dir: Path, name: str, color: tuple[int, int, int]) -> None:
        import cv2
        import numpy as np

        frames_dir.mkdir(parents=True, exist_ok=True)
        img = np.full((60, 80, 3), color, dtype=np.uint8)
        cv2.imwrite(str(frames_dir / name), img)

    def _make_blurred_frame(self, frames_dir: Path, name: str) -> None:
        import cv2
        import numpy as np

        frames_dir.mkdir(parents=True, exist_ok=True)
        checker = np.zeros((60, 80), dtype=np.uint8)
        checker[::4, ::4] = 255
        blurred = cv2.GaussianBlur(checker, (15, 15), 10)
        cv2.imwrite(str(frames_dir / name), cv2.cvtColor(blurred, cv2.COLOR_GRAY2BGR))

    def _make_sharp_frame(self, frames_dir: Path, name: str) -> None:
        import cv2
        import numpy as np

        frames_dir.mkdir(parents=True, exist_ok=True)
        checker = np.zeros((60, 80), dtype=np.uint8)
        checker[::2, ::2] = 255
        cv2.imwrite(str(frames_dir / name), cv2.cvtColor(checker, cv2.COLOR_GRAY2BGR))

    def test_ignore_blank_drops_solid_color_frames(self, tmp_path):
        self._make_solid_frame(tmp_path, "blank.jpg", (128, 128, 128))
        assert FrameAnalyzer.is_blank(str(tmp_path / "blank.jpg")) is True

    def test_sharp_frame_is_not_blank_or_blurred(self, tmp_path):
        self._make_sharp_frame(tmp_path, "sharp.jpg")
        assert FrameAnalyzer.is_blank(str(tmp_path / "sharp.jpg")) is False
        assert FrameAnalyzer.is_blurred(str(tmp_path / "sharp.jpg")) is False

    def test_blurred_frame_detected(self, tmp_path):
        self._make_blurred_frame(tmp_path, "blurred.jpg")
        assert FrameAnalyzer.is_blurred(str(tmp_path / "blurred.jpg"), threshold=200.0) is True

    def test_sharpness_ranks_sharp_above_blurred(self, tmp_path):
        self._make_sharp_frame(tmp_path, "sharp.jpg")
        self._make_blurred_frame(tmp_path, "blurred.jpg")
        assert FrameAnalyzer.sharpness(str(tmp_path / "sharp.jpg")) > FrameAnalyzer.sharpness(str(tmp_path / "blurred.jpg"))

    def test_dedup_visual_collapses_identical_frames(self, tmp_path):
        self._make_solid_frame(tmp_path, "a.jpg", (10, 10, 10))
        self._make_solid_frame(tmp_path, "b.jpg", (10, 10, 10))
        self._make_solid_frame(tmp_path, "c.jpg", (250, 10, 10))
        frames = [("a.jpg", 0.0), ("b.jpg", 0.5), ("c.jpg", 1.0)]
        result = _dedup_visual(tmp_path, frames, keep_best_quality=False)
        assert [n for n, _ in result] == ["a.jpg", "c.jpg"]

    def test_dedup_keep_best_quality_picks_sharper_of_group(self, tmp_path):
        self._make_blurred_frame(tmp_path, "blurry_dup.jpg")
        # Near-identical (same base pattern, slightly less blur) so they fall in one dedup group.
        import cv2
        import numpy as np

        checker = np.zeros((60, 80), dtype=np.uint8)
        checker[::4, ::4] = 255
        less_blurred = cv2.GaussianBlur(checker, (5, 5), 2)
        cv2.imwrite(str(tmp_path / "sharper_dup.jpg"), cv2.cvtColor(less_blurred, cv2.COLOR_GRAY2BGR))

        frames = [("blurry_dup.jpg", 0.0), ("sharper_dup.jpg", 0.1)]
        result = _dedup_visual(tmp_path, frames, keep_best_quality=True)
        assert len(result) == 1
        assert result[0][0] == "sharper_dup.jpg"

    def test_subsample_caps_and_spreads_evenly(self):
        frames = [(f"f{i}.jpg", float(i)) for i in range(20)]
        result = _subsample(frames, 5)
        assert len(result) == 5
        assert result[0][0] == "f0.jpg"

    def test_subsample_noop_when_under_cap(self):
        frames = [(f"f{i}.jpg", float(i)) for i in range(3)]
        assert _subsample(frames, 10) == frames

    def test_apply_filters_deletes_dropped_files_from_disk(self, tmp_path):
        self._make_sharp_frame(tmp_path, "keep.jpg")
        self._make_solid_frame(tmp_path, "blank.jpg", (128, 128, 128))
        frames = [("keep.jpg", 0.0), ("blank.jpg", 0.5)]
        opts = ExtractionOptions(ignore_blank=True, ignore_blurred=False, remove_duplicates=False, max_frames=0)
        result = _apply_filters(tmp_path, frames, opts)
        assert [n for n, _ in result] == ["keep.jpg"]
        assert (tmp_path / "keep.jpg").exists()
        assert not (tmp_path / "blank.jpg").exists()

    def test_apply_filters_unlimited_max_frames_keeps_everything(self, tmp_path):
        for i in range(5):
            self._make_solid_frame(tmp_path, f"f{i}.jpg", (i * 40, 10, 10))
        frames = [(f"f{i}.jpg", float(i)) for i in range(5)]
        opts = ExtractionOptions(ignore_blank=False, ignore_blurred=False, remove_duplicates=False, max_frames=0)
        result = _apply_filters(tmp_path, frames, opts)
        assert len(result) == 5

    def test_apply_filters_explicit_cap_subsamples(self, tmp_path):
        for i in range(10):
            self._make_solid_frame(tmp_path, f"f{i}.jpg", (i * 25, 10, 10))
        frames = [(f"f{i}.jpg", float(i)) for i in range(10)]
        opts = ExtractionOptions(ignore_blank=False, ignore_blurred=False, remove_duplicates=False, max_frames=3)
        result = _apply_filters(tmp_path, frames, opts)
        assert len(result) == 3
