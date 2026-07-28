"""Frame extraction: Strategy Pattern.

Every acquisition source (YouTube, Instagram, future sources) already downloads
a single local video.mp4 before this stage runs (see
`integrations/video_providers.py`). This service only decides WHICH frames get
pulled from that file -- every strategy returns the same
`list[tuple[filename, timestamp]]` shape `core/worker.py` already expects from
the old `FFmpeg.extract_frames` call, so nothing downstream (Frame rows, OCR,
analysis, classification, question extraction) changes.
"""
import difflib
import json
import re
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.config.settings import settings
from app.integrations.ffmpeg import FFmpeg
from app.integrations.frame_analysis import FrameAnalyzer
from app.integrations.ocr import OCR

STRATEGIES = ("fixed_interval", "scene_detection", "ocr_text_change", "hybrid", "all_frames")
DEFAULT_STRATEGY = "hybrid"

_WS_RE = re.compile(r"\s+")


#: Frame Sampling Mode offered in the UI. None = every decoded frame (catches
#: sub-300ms flash content); otherwise a target fps. Consumed by Scene
#: Detection, OCR Text Change and Hybrid -- Fixed Interval keeps its own
#: dedicated `interval` control and ignores this (unchanged strategy).
SAMPLING_FPS_OPTIONS: tuple[float | None, ...] = (None, 30.0, 15.0, 10.0, 5.0, 2.0, 1.0)
DEFAULT_SAMPLING_FPS = 10.0


@dataclass
class ExtractionOptions:
    strategy: str = DEFAULT_STRATEGY
    interval: float | None = None                  # Fixed Interval (seconds); None = auto
    scene_threshold: float = 0.35                   # Scene Detection / Hybrid sensitivity
    sampling_fps: float | None = DEFAULT_SAMPLING_FPS  # Frame Sampling Mode; None = every decoded frame
    max_frames: int | None = None      # None = auto cap, 0 = unlimited, N = hard cap
    remove_duplicates: bool = True
    keep_best_quality: bool = True
    ignore_blank: bool = True
    ignore_blurred: bool = True

    @classmethod
    def from_job(cls, job) -> "ExtractionOptions":
        try:
            opts = json.loads(job.extraction_options) if job.extraction_options else {}
        except json.JSONDecodeError:
            opts = {}
        strategy = job.extraction_strategy if job.extraction_strategy in STRATEGIES else DEFAULT_STRATEGY
        return cls(
            strategy=strategy,
            interval=opts.get("interval"),
            scene_threshold=opts.get("scene_threshold", 0.35),
            sampling_fps=opts.get("sampling_fps", DEFAULT_SAMPLING_FPS),
            max_frames=opts.get("max_frames"),
            remove_duplicates=opts.get("remove_duplicates", True),
            keep_best_quality=opts.get("keep_best_quality", True),
            ignore_blank=opts.get("ignore_blank", True),
            ignore_blurred=opts.get("ignore_blurred", True),
        )

    @classmethod
    def from_payload(cls, payload) -> "ExtractionOptions":
        """Build options from an API request payload (e.g. `JobCreate`) --
        duck-typed so this service never has to import the API layer."""
        return cls(
            strategy=payload.strategy if payload.strategy in STRATEGIES else DEFAULT_STRATEGY,
            interval=payload.interval,
            scene_threshold=payload.scene_threshold,
            sampling_fps=payload.sampling_fps,
            max_frames=payload.max_frames,
            remove_duplicates=payload.remove_duplicates,
            keep_best_quality=payload.keep_best_quality,
            ignore_blank=payload.ignore_blank,
            ignore_blurred=payload.ignore_blurred,
        )

    def options_json(self) -> str:
        return json.dumps({
            "interval": self.interval,
            "scene_threshold": self.scene_threshold,
            "sampling_fps": self.sampling_fps,
            "max_frames": self.max_frames,
            "remove_duplicates": self.remove_duplicates,
            "keep_best_quality": self.keep_best_quality,
            "ignore_blank": self.ignore_blank,
            "ignore_blurred": self.ignore_blurred,
        })


# --- text-diff helpers (OCR Text Change / Hybrid) ---

def _normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip().lower())


def _text_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _keep_on_text_change(
    candidates_dir: Path,
    candidates: list[tuple[str, float]],
    output_dir: Path,
    prefix: str,
    similarity_threshold: float = 0.85,
    collapse_empty_text: bool = True,
) -> list[tuple[str, float]]:
    """OCR each candidate frame; keep it only if its text differs meaningfully
    from the last KEPT frame's text (the Save/Skip pipeline). Kept frames are
    copied into `output_dir`; `candidates_dir` is left for the caller to clean up.

    `collapse_empty_text=False` (used by Hybrid, where candidates already passed
    scene detection) never skips on "both frames have no text" -- two textless
    frames (a diagram change, a camera cut) are not "the same" just because OCR
    found nothing; skipping them would silently undo scene detection's decision.
    Plain OCR Text Change (no prior scene filter) keeps the default: a run of
    textless frames collapses to one, since its only signal is text content."""
    output_dir.mkdir(parents=True, exist_ok=True)
    kept: list[tuple[str, float]] = []
    last_text: str | None = None
    for i, (filename, ts) in enumerate(candidates):
        path = candidates_dir / filename
        text, _ = OCR.read_image_detailed(str(path))
        norm = _normalize_text(text)
        both_empty = not norm and not (last_text or "")
        if (
            last_text is not None
            and not (both_empty and not collapse_empty_text)
            and _text_similarity(norm, last_text) >= similarity_threshold
        ):
            continue
        last_text = norm
        out_name = f"{prefix}_{i:05d}.jpg"
        shutil.copyfile(path, output_dir / out_name)
        kept.append((out_name, ts))
    return kept


def _prepend_first_frame(
    video_path: str, frames_dir: Path, frames: list[tuple[str, float]], prefix: str
) -> list[tuple[str, float]]:
    """Scene detection only fires on a change, so it never selects frame 0 --
    extract the opening frame directly so it's never silently dropped."""
    if frames and frames[0][1] <= 0.05:
        return frames
    filename = f"{prefix}_00000.jpg"
    FFmpeg.extract_single_frame(video_path, frames_dir, filename, 0.0)
    return [(filename, 0.0), *frames]


# --- strategies ---

class FrameExtractionStrategy(ABC):
    @abstractmethod
    def extract(
        self, video_path: str, frames_dir: Path, options: ExtractionOptions, duration: float
    ) -> list[tuple[str, float]]:
        ...


class FixedIntervalStrategy(FrameExtractionStrategy):
    """Uniform time-based sampling -- the original behaviour, now with a
    user-selectable interval down to 0.25s so brief content isn't skipped."""

    def extract(self, video_path, frames_dir, options, duration):
        interval = options.interval
        if not interval:
            cap = options.max_frames or settings.frame_max_count
            interval = max(settings.frame_min_interval, duration / cap) if duration > 0 else settings.frame_min_interval
        return FFmpeg.extract_frames(video_path, frames_dir, interval)


class SceneDetectionStrategy(FrameExtractionStrategy):
    """Extract only when the visual scene changes significantly (new slide,
    question appears, diagram changes, camera cut). `sampling_fps` controls how
    many decoded frames feed the scene comparison (None = every frame, so a
    100-300ms flash cut is never skipped between samples)."""

    def extract(self, video_path, frames_dir, options, duration):
        frames = FFmpeg.extract_frames_scene(
            video_path, frames_dir, options.scene_threshold, sample_fps=options.sampling_fps
        )
        return _prepend_first_frame(video_path, frames_dir, frames, prefix="scene")


class OCRTextChangeStrategy(FrameExtractionStrategy):
    """Frame Sampling stage examines frames at `options.sampling_fps` (None =
    every decoded frame); OCR each candidate and keep a frame only when its
    text differs from the previously kept frame's text."""

    def extract(self, video_path, frames_dir, options, duration):
        sample_dir = frames_dir / "_sample"
        try:
            candidates = FFmpeg.extract_frames_sampled(video_path, sample_dir, options.sampling_fps)
            return _keep_on_text_change(sample_dir, candidates, frames_dir, prefix="ocrtext")
        finally:
            shutil.rmtree(sample_dir, ignore_errors=True)


class AllFramesStrategy(FrameExtractionStrategy):
    """No scene/text-diff filtering at all -- keeps every frame `sampling_fps`
    decodes (None = every single decoded frame, matching the video's native
    frame rate). The Advanced quality checkboxes (blank/blur/dedup/cap) still
    apply afterward if the caller enables them; off by default this is a
    literal "extract everything" strategy for short clips."""

    def extract(self, video_path, frames_dir, options, duration):
        return FFmpeg.extract_frames_sampled(video_path, frames_dir, options.sampling_fps)


class HybridStrategy(FrameExtractionStrategy):
    """Recommended default: Frame Sampling feeds scene detection (which narrows
    candidates), OCR text-diff drops near-duplicate slides, and the shared
    quality filters (below) then drop blank/blurred frames and collapse any
    remaining visual duplicates."""

    def extract(self, video_path, frames_dir, options, duration):
        scene_dir = frames_dir / "_scene"
        try:
            scene_frames = FFmpeg.extract_frames_scene(
                video_path, scene_dir, options.scene_threshold, sample_fps=options.sampling_fps
            )
            scene_frames = _prepend_first_frame(video_path, scene_dir, scene_frames, prefix="scene")
            return _keep_on_text_change(
                scene_dir, scene_frames, frames_dir, prefix="hybrid", collapse_empty_text=False
            )
        finally:
            shutil.rmtree(scene_dir, ignore_errors=True)


# --- shared post-extraction filters (Advanced options, apply to every strategy) ---

def _drop(frames_dir: Path, frames: list[tuple[str, float]], predicate: Callable[[str], bool]) -> list[tuple[str, float]]:
    return [(name, ts) for name, ts in frames if not predicate(str(frames_dir / name))]


def _dedup_visual(frames_dir: Path, frames: list[tuple[str, float]], keep_best_quality: bool) -> list[tuple[str, float]]:
    """Collapse consecutive near-identical frames (pixel signature), same
    algorithm as the review-queue dedup (`FrameAnalyzer.signature`/`difference`),
    but here duplicates are dropped rather than just flagged."""
    if not frames:
        return frames
    groups: list[list[tuple[str, float]]] = [[frames[0]]]
    last_sig = FrameAnalyzer.signature(str(frames_dir / frames[0][0]))
    for name, ts in frames[1:]:
        sig = FrameAnalyzer.signature(str(frames_dir / name))
        if FrameAnalyzer.difference(sig, last_sig) <= settings.dedup_mad:
            groups[-1].append((name, ts))
        else:
            groups.append([(name, ts)])
            last_sig = sig

    representatives = []
    for group in groups:
        if len(group) == 1 or not keep_best_quality:
            representatives.append(group[0])
        else:
            best = max(group, key=lambda item: FrameAnalyzer.sharpness(str(frames_dir / item[0])))
            representatives.append(best)
    return representatives


def _subsample(frames: list[tuple[str, float]], cap: int) -> list[tuple[str, float]]:
    if cap <= 0 or len(frames) <= cap:
        return frames
    step = len(frames) / cap
    indices = sorted({int(i * step) for i in range(cap)})
    return [frames[i] for i in indices]


def _apply_filters(frames_dir: Path, frames: list[tuple[str, float]], options: ExtractionOptions) -> list[tuple[str, float]]:
    original = frames
    kept = frames

    if options.ignore_blank:
        kept = _drop(frames_dir, kept, FrameAnalyzer.is_blank)
    if options.ignore_blurred:
        kept = _drop(frames_dir, kept, FrameAnalyzer.is_blurred)
    if options.remove_duplicates:
        kept = _dedup_visual(frames_dir, kept, options.keep_best_quality)

    cap = options.max_frames
    if cap is None:
        cap = settings.frame_max_count
    if cap:
        kept = _subsample(kept, cap)

    kept_names = {name for name, _ in kept}
    for name, _ in original:
        if name not in kept_names:
            (frames_dir / name).unlink(missing_ok=True)
    return kept


class FrameExtractionService:
    """Facade: acquisition workers call this instead of an integration
    directly, so adding a new strategy never touches `core/worker.py`."""

    _STRATEGIES: dict[str, FrameExtractionStrategy] = {
        "fixed_interval": FixedIntervalStrategy(),
        "scene_detection": SceneDetectionStrategy(),
        "ocr_text_change": OCRTextChangeStrategy(),
        "hybrid": HybridStrategy(),
        "all_frames": AllFramesStrategy(),
    }

    def extract(
        self, video_path: str, frames_dir: Path, options: ExtractionOptions, duration: float
    ) -> list[tuple[str, float]]:
        strategy = self._STRATEGIES.get(options.strategy, self._STRATEGIES[DEFAULT_STRATEGY])
        frames = strategy.extract(video_path, frames_dir, options, duration)
        return _apply_filters(frames_dir, frames, options)
