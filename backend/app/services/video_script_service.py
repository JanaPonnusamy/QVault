"""Speaking-script generation for video narration.

The narrator never reads raw JSON — every question is turned into a natural
conversational script (intro phrase, question, spoken options, thinking cue,
answer reveal, explanation) with deliberate pauses between segments. Each
segment is synthesized separately so the visual timeline can be derived
exactly from real audio durations rather than estimates.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.video_source_service import QuestionItem

OPTION_LETTERS = ["A", "B", "C", "D"]

_QUESTION_LEADS = [
    "Here's your next question.",
    "Let's move on. Question {n}.",
    "Try this one.",
    "Question {n}. Ready?",
    "Here comes the next one.",
]

_SHORT_HOOKS = [
    "Can you answer this?",
    "Only a genius gets this right!",
    "Let's test your knowledge!",
    "How fast can you answer this?",
]

EXPLANATION_CHAR_BUDGET = {"video": 340, "short": 160}  # shorts stay in the 20-35s window


@dataclass
class ScriptSegment:
    role: str  # intro | question | option | think | reveal | explanation | outro
    text: str
    pause_after: float = 0.0
    scene_index: int = -1  # -1 for intro/outro
    option_index: int = -1


def trim_solution(solution: str, budget: int) -> str:
    """First sentences of the solution up to a character budget."""
    text = " ".join(solution.split())
    if not text:
        return ""
    sentences: list[str] = []
    total = 0
    for part in text.replace("? ", "?|").replace("! ", "!|").replace(". ", ".|").split("|"):
        part = part.strip()
        if not part:
            continue
        if sentences and total + len(part) > budget:
            break
        sentences.append(part)
        total += len(part) + 1
    trimmed = " ".join(sentences)
    if len(trimmed) > budget:
        trimmed = trimmed[: budget - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return trimmed


class VideoScriptService:
    """Builds the full narration script for one video."""

    def build(self, questions: list[QuestionItem], kind: str, category: str) -> list[ScriptSegment]:
        segments: list[ScriptSegment] = []
        is_short = kind != "video"
        budget = EXPLANATION_CHAR_BUDGET["short" if is_short else "video"]

        if is_short:
            hook = _SHORT_HOOKS[hash(questions[0].id) % len(_SHORT_HOOKS)]
            segments.append(ScriptSegment("intro", hook, pause_after=0.3))
        else:
            segments.append(
                ScriptSegment(
                    "intro",
                    f"Welcome to today's {category} quiz! "
                    f"We have {len(questions)} questions for you. Let's begin!",
                    pause_after=0.6,
                )
            )

        for index, item in enumerate(questions):
            segments.extend(self._question_segments(item, index, is_short, budget))

        outro = (
            "Follow for more quick quizzes!"
            if is_short
            else "That's all for today! Comment your score below, "
            "and subscribe for more quizzes like this one."
        )
        segments.append(ScriptSegment("outro", outro, pause_after=0.5))
        return segments

    def _question_segments(
        self, item: QuestionItem, index: int, is_short: bool, budget: int
    ) -> list[ScriptSegment]:
        segments: list[ScriptSegment] = []

        question_text = item.question if is_short else self._lead(index) + " " + item.question
        segments.append(ScriptSegment("question", question_text, pause_after=0.4, scene_index=index))

        for opt_index, option in enumerate(item.options):
            segments.append(
                ScriptSegment(
                    "option",
                    f"Option {OPTION_LETTERS[opt_index]}. {option}.",
                    pause_after=0.15,
                    scene_index=index,
                    option_index=opt_index,
                )
            )

        segments.append(
            ScriptSegment("think", "Take a moment to think.", pause_after=0.2, scene_index=index)
        )
        segments.append(
            ScriptSegment(
                "reveal",
                f"The correct answer is, {item.answer_text}.",
                pause_after=0.5,
                scene_index=index,
            )
        )
        explanation = trim_solution(item.solution, budget)
        if explanation:
            segments.append(
                ScriptSegment("explanation", explanation, pause_after=0.7, scene_index=index)
            )
        return segments

    @staticmethod
    def _lead(index: int) -> str:
        if index == 0:
            return "Here's your first question."
        return _QUESTION_LEADS[index % len(_QUESTION_LEADS)].format(n=index + 1)
