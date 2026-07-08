import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.integrations.ocr import OCR
from app.models.extraction import ExtractionJob, Frame

# Deterministic content-type classification of OCR'd frame text. No AI.
# Reuses the same option pattern as the question-merge stage.
_OPTION = re.compile(r"^\s*(\(?[A-Da-d][\).]|[1-4][\).])\s+\S")
_ANSWER = re.compile(r"^\s*(answer|ans|correct\s+answer|solution|key)\b\s*[:.\-)]", re.I)
_QUESTION_LEAD = re.compile(
    r"^\s*(q\s*[.\d):\-]|question\b|(who|what|why|when|where|which|how|whose|whom)\b)", re.I
)
_DIAGRAM = re.compile(
    r"^\s*(fig(?:ure)?|diagram|image|photo|plate|chart|graph|illustration)\b[\s.:\-]*\d?", re.I
)
_TABLE = re.compile(r"^\s*table\b[\s.:\-]*\d", re.I)
_COLUMNS = re.compile(r"\S {2,}\S")

# Ordered so callers can render a stable set of badges.
CLASSES = ("heading", "paragraph", "question", "options", "answer", "diagram", "table")


def classify(text: str) -> list[str]:
    """Classify a frame's OCR text into structural content types.

    A single frame may legitimately carry several types (e.g. a question stem
    plus its options), so this returns the set of detected classes. Deterministic
    and regex-driven — no AI, no knowledge generation.
    """
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return []

    tags: set[str] = set()
    tabular_rows = 0
    for line in lines:
        if _OPTION.match(line):
            tags.add("options")
            continue
        if _ANSWER.match(line):
            tags.add("answer")
            continue
        if _TABLE.match(line):
            tags.add("table")
        if _DIAGRAM.match(line):
            tags.add("diagram")
        if line.endswith("?") or _QUESTION_LEAD.match(line):
            tags.add("question")
        if "\t" in line or len(_COLUMNS.findall(line)) >= 2:
            tabular_rows += 1

    if tabular_rows >= 2:
        tags.add("table")
    if "options" in tags:
        tags.add("question")

    words = " ".join(lines).split()
    only_line = lines[0]
    is_short_single = (
        len(lines) == 1
        and len(only_line.split()) <= 8
        and not only_line.endswith((".", "?", "!", ":", ";"))
    )
    if is_short_single and tags.isdisjoint({"question", "options", "answer", "diagram", "table"}):
        if only_line.isupper() or only_line.istitle() or len(only_line.split()) <= 5:
            tags.add("heading")

    structural = {"heading", "question", "options", "answer", "diagram", "table"}
    if not tags:
        tags.add("paragraph")
    elif tags.isdisjoint(structural):
        tags.add("paragraph")
    elif tags <= {"heading", "diagram"} and len(words) >= 12:
        # A "heading"/caption carrying a full sentence of prose is really a paragraph.
        tags.discard("heading")
        tags.add("paragraph")

    return [c for c in CLASSES if c in tags]


class ClassificationService:
    """Basic classification for acquired video frames (Instagram and future sources).

    Ensures every non-duplicate frame with visible text is OCR'd, then tags its
    content type. Reuses the shared OCR engine and the existing `frames` table
    (`classification` column); creates nothing new.
    """

    def __init__(self, db: Session):
        self.db = db

    def process_job(self, job_id: int) -> dict:
        job = self.db.get(ExtractionJob, job_id)
        if not job:
            return {"frames": 0, "classified": 0}

        frames = list(
            self.db.scalars(
                select(Frame)
                .where(Frame.job_id == job_id, Frame.is_duplicate == False)  # noqa: E712
                .order_by(Frame.index)
            )
        )

        classified = 0
        for frame in frames:
            if not frame.ocr_done:
                path = settings.jobs_dir / str(job_id) / "frames" / frame.filename
                text, confidence = OCR.read_image_detailed(str(path))
                frame.ocr_text = text
                frame.ocr_confidence = confidence
                frame.ocr_done = True
            tags = classify(frame.ocr_text)
            frame.classification = json.dumps(tags)
            if tags:
                classified += 1

        self.db.commit()
        return {"frames": len(frames), "classified": classified}
