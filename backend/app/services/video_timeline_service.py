"""Deterministic video timeline built from real narration audio.

Every script segment is synthesized first (with an on-disk cache keyed by
provider/voice/text), then the visual event times — question in, options in,
thinking pause, countdown, answer reveal/highlight, answer card, explanation —
are derived exactly from the measured audio durations. The same timeline
drives both landscape and portrait rendering; only the layout differs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from app.config.settings import settings
from app.integrations.tts import WordTiming, get_tts_provider
from app.services.video_script_service import (
    EXPLANATION_CHAR_BUDGET,
    ScriptSegment,
    VideoScriptService,
    trim_solution,
)
from app.services.video_source_service import QuestionItem
from app.shared.logging import get_logger

logger = get_logger("video_timeline")

COUNTDOWN_SECONDS = 3
QUESTION_CARD_LEAD = 0.35  # card animates in before its narration starts
ANSWER_CARD_DELAY = 0.9  # answer card slides in while reveal narration plays
SCENE_TAIL = 0.35  # transition gap between questions
LEAD_IN = 0.6
TAIL_OUT = 0.8


@dataclass
class SubtitleWord:
    text: str
    start: float
    end: float


@dataclass
class CaptionChunk:
    words: list[SubtitleWord]
    start: float
    end: float


@dataclass
class AudioClip:
    path: str
    start: float


@dataclass
class SceneTimeline:
    index: int
    question: QuestionItem
    explanation_text: str
    question_in: float = 0.0
    option_in: list[float] = field(default_factory=list)
    think_in: float = 0.0
    countdown_in: float = 0.0
    reveal_at: float = 0.0
    answer_in: float = 0.0
    explanation_in: float | None = None
    end: float = 0.0


@dataclass
class VideoTimeline:
    kind: str  # video | short | reel
    category: str
    intro_end: float
    scenes: list[SceneTimeline]
    outro_in: float
    duration: float
    audio_clips: list[AudioClip]
    captions: list[CaptionChunk]
    tick_times: list[float]
    countdown_seconds: int = COUNTDOWN_SECONDS

    def preview(self) -> dict:
        """JSON-safe structure for the timeline preview API."""
        return {
            "kind": self.kind,
            "category": self.category,
            "duration": round(self.duration, 2),
            "intro_end": round(self.intro_end, 2),
            "outro_in": round(self.outro_in, 2),
            "scenes": [
                {
                    "index": s.index,
                    "question": s.question.question,
                    "answer": s.question.answer_text,
                    "question_in": round(s.question_in, 2),
                    "options_in": [round(t, 2) for t in s.option_in],
                    "think_in": round(s.think_in, 2),
                    "countdown_in": round(s.countdown_in, 2),
                    "reveal_at": round(s.reveal_at, 2),
                    "answer_in": round(s.answer_in, 2),
                    "explanation_in": round(s.explanation_in, 2) if s.explanation_in else None,
                    "end": round(s.end, 2),
                }
                for s in self.scenes
            ],
        }


def _estimate_words(text: str, duration: float) -> list[WordTiming]:
    """Proportional fallback for providers without word-boundary events."""
    tokens = text.split()
    if not tokens:
        return []
    weights = [len(t) + 2 for t in tokens]
    total = sum(weights)
    words, cursor = [], 0.0
    for token, weight in zip(tokens, weights):
        span = duration * weight / total
        words.append(WordTiming(word=token, start=cursor, end=cursor + span))
        cursor += span
    return words


class VideoTimelineService:
    """Synthesizes narration and lays segments out on the clock."""

    def __init__(self) -> None:
        self.script_service = VideoScriptService()
        self.cache_dir = settings.output_dir / ".work" / "tts_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def build(
        self,
        questions: list[QuestionItem],
        kind: str,
        category: str,
        provider_name: str | None = None,
        voice: str | None = None,
        progress=None,
    ) -> VideoTimeline:
        provider = get_tts_provider(provider_name)
        segments = self.script_service.build(questions, kind, category)

        synth: list[tuple[ScriptSegment, float, list[WordTiming], Path]] = []
        for i, segment in enumerate(segments):
            path, duration, words = self._synthesize_cached(provider, segment.text, voice)
            synth.append((segment, duration, words, path))
            if progress:
                progress(int(5 + 40 * (i + 1) / len(segments)), "Synthesizing narration")

        return self._layout(questions, kind, category, synth)

    def estimate(self, questions: list[QuestionItem], kind: str, category: str) -> VideoTimeline:
        """Timeline preview without synthesizing audio (~2.5 words/sec estimate)."""
        segments = self.script_service.build(questions, kind, category)
        synth = []
        for segment in segments:
            duration = 0.5 + len(segment.text.split()) / 2.5
            synth.append(
                (segment, duration, _estimate_words(segment.text, duration), Path(""))
            )
        return self._layout(questions, kind, category, synth)

    def _synthesize_cached(self, provider, text: str, voice: str | None):
        effective_voice = voice or settings.tts_voice
        key = hashlib.sha1(
            "|".join(
                [provider.name, effective_voice, settings.tts_rate, settings.tts_pitch, text]
            ).encode("utf-8")
        ).hexdigest()
        audio_path = self.cache_dir / f"{key}.mp3"
        meta_path = self.cache_dir / f"{key}.json"
        if audio_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            words = [WordTiming(**w) for w in meta["words"]]
            return audio_path, meta["duration"], words

        result = provider.synthesize(text, effective_voice, audio_path)
        words = result.words or _estimate_words(text, result.duration)
        meta_path.write_text(
            json.dumps(
                {
                    "duration": result.duration,
                    "words": [{"word": w.word, "start": w.start, "end": w.end} for w in words],
                }
            ),
            encoding="utf-8",
        )
        return audio_path, result.duration, words

    def _layout(self, questions, kind, category, synth) -> VideoTimeline:
        audio_clips: list[AudioClip] = []
        all_words: list[SubtitleWord] = []
        tick_times: list[float] = []
        budget = EXPLANATION_CHAR_BUDGET["short" if kind != "video" else "video"]

        scene_map: dict[int, SceneTimeline] = {
            index: SceneTimeline(
                index=index,
                question=item,
                explanation_text=trim_solution(item.solution, budget),
                option_in=[0.0] * len(item.options),
            )
            for index, item in enumerate(questions)
        }

        cursor = LEAD_IN
        intro_end = cursor

        def place(segment: ScriptSegment, duration: float, words, path: Path) -> float:
            nonlocal cursor
            start = cursor
            audio_clips.append(AudioClip(path=str(path), start=start))
            for w in words:
                all_words.append(
                    SubtitleWord(text=w.word, start=start + w.start, end=start + w.end)
                )
            cursor = start + duration + segment.pause_after
            return start

        for segment, duration, words, path in synth:
            if segment.role == "intro":
                place(segment, duration, words, path)
                intro_end = cursor + 0.2
                cursor = intro_end
            elif segment.role == "question":
                scene = scene_map[segment.scene_index]
                scene.question_in = cursor
                cursor += QUESTION_CARD_LEAD
                place(segment, duration, words, path)
            elif segment.role == "option":
                scene = scene_map[segment.scene_index]
                scene.option_in[segment.option_index] = cursor
                place(segment, duration, words, path)
            elif segment.role == "think":
                scene = scene_map[segment.scene_index]
                scene.think_in = cursor
                place(segment, duration, words, path)
                scene.countdown_in = cursor
                for i in range(COUNTDOWN_SECONDS):
                    tick_times.append(cursor + i)
                cursor += COUNTDOWN_SECONDS + 0.35
            elif segment.role == "reveal":
                scene = scene_map[segment.scene_index]
                scene.reveal_at = cursor
                scene.answer_in = cursor + ANSWER_CARD_DELAY
                place(segment, duration, words, path)
            elif segment.role == "explanation":
                scene = scene_map[segment.scene_index]
                scene.explanation_in = cursor
                place(segment, duration, words, path)
                scene.end = cursor + SCENE_TAIL
                cursor = scene.end

        # scenes without an explanation still need their end stamped
        for scene in scene_map.values():
            if scene.end == 0.0:
                scene.end = max(scene.answer_in + 1.4, cursor) + SCENE_TAIL
                cursor = max(cursor, scene.end)

        outro_in = cursor
        for segment, duration, words, path in synth:
            if segment.role == "outro":
                place(segment, duration, words, path)

        return VideoTimeline(
            kind=kind,
            category=category,
            intro_end=intro_end,
            scenes=[scene_map[i] for i in sorted(scene_map)],
            outro_in=outro_in,
            duration=cursor + TAIL_OUT,
            audio_clips=audio_clips,
            captions=self._chunk_captions(all_words),
            tick_times=tick_times,
        )

    @staticmethod
    def _chunk_captions(words: list[SubtitleWord], max_chars: int = 34) -> list[CaptionChunk]:
        chunks: list[CaptionChunk] = []
        current: list[SubtitleWord] = []
        length = 0
        for word in words:
            # a silence gap (>0.9s) between words ends the caption line
            gap = bool(current) and word.start - current[-1].end > 0.9
            if current and (length + len(word.text) + 1 > max_chars or gap):
                chunks.append(CaptionChunk(current, current[0].start, current[-1].end))
                current, length = [], 0
            current.append(word)
            length += len(word.text) + 1
        if current:
            chunks.append(CaptionChunk(current, current[0].start, current[-1].end))
        return chunks
