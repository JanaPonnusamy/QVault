import json
import re
from math import ceil

from sqlalchemy.orm import Session

from app.models.content import ContentBlock, ContentSection
from app.models.document import Document
from app.repositories.content_repository import ContentRepository
from app.repositories.document_repository import DocumentRepository

_CAPTION = re.compile(r"^(fig(?:ure)?|table|image|photo|plate|chart|diagram|exhibit)\b[\s.:\-]*\d", re.I)
_EXAMPLE = re.compile(r"^\s*example\b", re.I)
_EXERCISE = re.compile(r"^\s*(exercises?|questions|problems)\b", re.I)
_PAGE_NUMBER = re.compile(r"^\s*(page\s*)?[ivxlcdm\d]{1,6}\s*$", re.I)
_SENTENCE_END = (".", "!", "?", ":", ";", ")", '"', "”")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _parse(extra: str) -> dict | None:
    if not extra:
        return None
    try:
        return json.loads(extra)
    except json.JSONDecodeError:
        return None


class ContentAssemblyService:
    """Deterministically reconstruct readable content from raw `document_elements`.

    Responsibilities: drop page numbers + running headers/footers, merge adjacent
    text into paragraphs (handling hyphenation), associate captions with figures/
    tables, recognise headings/examples/exercises, preserve reading order, and
    group content into logical sections. No AI, no OCR.

    The raw extraction (`document_elements`/`document_bookmarks`) is never modified;
    output goes to the separate `content_sections`/`content_blocks` tables and is
    fully regenerable.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = ContentRepository(db)
        self.docs = DocumentRepository(db)

    def clear(self, document_id: int) -> None:
        self.repo.clear_for_document(document_id)

    def assemble(self, document: Document) -> dict:
        self.repo.clear_for_document(document.id)
        elements = self.docs.elements(document.id)

        noise = self._detect_noise(elements, document.page_count)
        clean = [e for e in elements if e.id not in noise]

        self._order = 0
        self._blocks: list[ContentBlock] = []
        root = self.repo.add_section(
            ContentSection(document_id=document.id, parent_id=None,
                           title=document.title or f"Document {document.id}", level=0, order_index=0)
        )
        self._section_order = 1
        stack: list[tuple[int, ContentSection]] = [(0, root)]

        # paragraph merge buffers
        buf_text: list[str] = []
        buf_ids: list[int] = []
        buf_type = "paragraph"
        buf_page = 0
        pending_caption: tuple[str, list[int]] | None = None

        def flush_para():
            nonlocal buf_text, buf_ids, buf_type, buf_page
            if buf_text:
                self._emit(document.id, stack[-1][1].id, buf_type,
                           text=" ".join(buf_text).strip(), page=buf_page, element_ids=list(buf_ids))
            buf_text, buf_ids, buf_type = [], [], "paragraph"

        for el in clean:
            etype = el.element_type
            text = (el.text or "").strip()

            if etype == "heading":
                flush_para()
                if pending_caption:
                    self._emit(document.id, stack[-1][1].id, "paragraph",
                               text=pending_caption[0], page=el.page, element_ids=pending_caption[1])
                    pending_caption = None
                level = el.level or 1
                while len(stack) > 1 and stack[-1][0] >= level:
                    stack.pop()
                parent = stack[-1][1]
                section = self.repo.add_section(ContentSection(
                    document_id=document.id, parent_id=parent.id, title=text,
                    level=level, order_index=self._section_order, page_start=el.page, page_end=el.page,
                ))
                self._section_order += 1
                stack.append((level, section))
                continue

            if etype in ("figure", "table"):
                flush_para()
                extra = _parse(el.extra)
                block = self._emit(document.id, stack[-1][1].id, etype, text="",
                                   page=el.page, element_ids=[el.id], extra=extra)
                if pending_caption:
                    block.caption = pending_caption[0]
                    block.source_element_ids = json.dumps([el.id, *pending_caption[1]])
                    pending_caption = None
                continue

            # paragraph-like element
            if not text:
                continue
            if _CAPTION.match(text):
                if self._blocks and self._blocks[-1].block_type in ("figure", "table") and not self._blocks[-1].caption:
                    self._blocks[-1].caption = text
                    ids = json.loads(self._blocks[-1].source_element_ids or "[]")
                    self._blocks[-1].source_element_ids = json.dumps([*ids, el.id])
                else:
                    pending_caption = (text, [el.id])
                continue

            is_example = bool(_EXAMPLE.match(text))
            is_exercise = bool(_EXERCISE.match(text))

            if is_example or is_exercise:
                flush_para()
                buf_type = "example" if is_example else "exercise"
                buf_text, buf_ids, buf_page = [text], [el.id], el.page
                continue

            # plain paragraph
            if buf_text and (buf_type in ("example", "exercise") or self._continues(buf_text[-1], text)):
                merged_prev, merged_cur = self._dehyphenate(buf_text[-1], text)
                buf_text[-1] = merged_prev
                if merged_cur:
                    buf_text.append(merged_cur)
                buf_ids.append(el.id)
            else:
                flush_para()
                buf_text, buf_ids, buf_type, buf_page = [text], [el.id], "paragraph", el.page

        flush_para()
        if pending_caption:
            self._emit(document.id, stack[-1][1].id, "paragraph",
                       text=pending_caption[0], page=0, element_ids=pending_caption[1])

        self.repo.add_blocks(self._blocks)
        self._set_section_pages()
        self.repo.commit()
        return {
            "sections": self._section_order,
            "blocks": len(self._blocks),
            "dropped_noise": len(noise),
        }

    # ---- helpers ----

    def _emit(self, document_id, section_id, block_type, text, page, element_ids, extra=None) -> ContentBlock:
        block = ContentBlock(
            document_id=document_id, section_id=section_id, block_type=block_type,
            order_index=self._order, text=text, page=page,
            source_element_ids=json.dumps(element_ids),
            extra=json.dumps(extra) if extra else "",
        )
        self._order += 1
        self._blocks.append(block)
        return block

    @staticmethod
    def _continues(prev: str, _nxt: str) -> bool:
        """A paragraph continues if the previous text did not end a sentence."""
        return bool(prev) and not prev.rstrip().endswith(_SENTENCE_END)

    @staticmethod
    def _dehyphenate(prev: str, nxt: str) -> tuple[str, str]:
        """Join a word split by a trailing hyphen at a line/page break."""
        if prev.rstrip().endswith("-"):
            stripped = prev.rstrip()[:-1]
            head, _, tail = nxt.partition(" ")
            return stripped + head, tail
        return prev, nxt

    def _detect_noise(self, elements, page_count: int) -> set[int]:
        """Page numbers + running headers/footers (text repeated across pages)."""
        noise: set[int] = set()
        text_pages: dict[str, set[int]] = {}
        text_ids: dict[str, list[int]] = {}

        for el in elements:
            if el.element_type not in ("paragraph", "heading"):
                continue
            text = (el.text or "").strip()
            if not text:
                continue
            if _PAGE_NUMBER.match(text) and len(text) <= 8:
                noise.add(el.id)
                continue
            if len(text) <= 80:
                key = _norm(text)
                text_pages.setdefault(key, set()).add(el.page)
                text_ids.setdefault(key, []).append(el.id)

        if page_count >= 3:
            threshold = max(3, ceil(0.4 * page_count))
            for key, pages in text_pages.items():
                if len(pages) >= threshold:
                    noise.update(text_ids[key])
        return noise

    def _set_section_pages(self) -> None:
        ranges: dict[int, list[int]] = {}
        for block in self._blocks:
            if block.section_id and block.page:
                ranges.setdefault(block.section_id, []).append(block.page)
        for section_id, pages in ranges.items():
            section = self.db.get(ContentSection, section_id)
            if section:
                section.page_start = min(pages)
                section.page_end = max(pages)
