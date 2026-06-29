from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import fitz  # PyMuPDF

_BOLD_FLAG = 1 << 4


@dataclass
class Element:
    element_type: str  # heading | paragraph | table | figure
    page: int
    text: str = ""
    level: int | None = None
    bbox: list[float] = field(default_factory=list)
    extra: dict | None = None
    order_index: int = 0


@dataclass
class ExtractedDocument:
    page_count: int
    has_text_layer: bool
    needs_ocr: bool
    elements: list[Element]
    bookmarks: list[dict]


def _body_size(doc: fitz.Document) -> float:
    """Most common font size weighted by character count = body text size."""
    weighted: Counter[int] = Counter()
    for page in doc:
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        weighted[round(span.get("size", 0))] += len(text)
    return float(weighted.most_common(1)[0][0]) if weighted else 12.0


def _heading_levels(doc: fitz.Document, body: float) -> dict[int, int]:
    """Map distinct heading font sizes (larger than body) to levels 1..N."""
    sizes: set[int] = set()
    for page in doc:
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            block_size = _block_size(block)
            if block_size >= body + 1.0:
                sizes.add(round(block_size))
    ordered = sorted(sizes, reverse=True)
    return {size: i + 1 for i, size in enumerate(ordered)}


def _block_size(block: dict) -> float:
    return max(
        (span.get("size", 0) for line in block.get("lines", []) for span in line.get("spans", [])),
        default=0.0,
    )


def _block_text(block: dict) -> str:
    lines = []
    for line in block.get("lines", []):
        text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
        if text:
            lines.append(text)
    return "\n".join(lines).strip()


def _block_is_bold(block: dict) -> bool:
    return any(
        span.get("flags", 0) & _BOLD_FLAG
        for line in block.get("lines", [])
        for span in line.get("spans", [])
    )


def _inside(bbox, rects) -> bool:
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    return any(r.x0 <= cx <= r.x1 and r.y0 <= cy <= r.y1 for r in rects)


class PdfExtractor:
    @staticmethod
    def extract(pdf_path: str) -> ExtractedDocument:
        doc = fitz.open(pdf_path)
        try:
            page_count = doc.page_count
            total_chars = sum(len(doc[i].get_text("text").strip()) for i in range(page_count))
            has_text_layer = total_chars >= max(1, page_count) * 20

            body = _body_size(doc)
            heading_levels = _heading_levels(doc, body)

            elements: list[Element] = []
            order = 0

            for page_index in range(page_count):
                page = doc[page_index]
                page_no = page_index + 1
                page_items: list[tuple[float, Element]] = []

                # Tables (ruled). Capture cells; exclude their text from paragraphs.
                table_rects = []
                try:
                    found = page.find_tables()
                    tables = found.tables
                except Exception:  # noqa: BLE001
                    tables = []
                for table in tables:
                    rect = fitz.Rect(table.bbox)
                    table_rects.append(rect)
                    rows = table.extract()
                    page_items.append((
                        rect.y0,
                        Element(
                            element_type="table",
                            page=page_no,
                            text="",
                            bbox=[rect.x0, rect.y0, rect.x1, rect.y1],
                            extra={"rows": rows, "n_rows": len(rows), "n_cols": len(rows[0]) if rows else 0},
                        ),
                    ))

                # Text blocks -> headings / paragraphs
                data = page.get_text("dict")
                for block in data.get("blocks", []):
                    if not block.get("lines"):
                        continue
                    bbox = block.get("bbox", [0, 0, 0, 0])
                    if _inside(bbox, table_rects):
                        continue
                    text = _block_text(block)
                    if not text:
                        continue
                    size = _block_size(block)
                    is_heading = round(size) in heading_levels and len(text) <= 200
                    if is_heading:
                        page_items.append((
                            bbox[1],
                            Element(
                                element_type="heading",
                                page=page_no,
                                text=text,
                                level=heading_levels[round(size)],
                                bbox=list(bbox),
                            ),
                        ))
                    else:
                        page_items.append((
                            bbox[1],
                            Element(element_type="paragraph", page=page_no, text=text, bbox=list(bbox)),
                        ))

                # Figures / images
                for info in page.get_image_info():
                    bbox = info.get("bbox")
                    if not bbox:
                        continue
                    page_items.append((
                        bbox[1],
                        Element(
                            element_type="figure",
                            page=page_no,
                            bbox=list(bbox),
                            extra={"width": info.get("width", 0), "height": info.get("height", 0)},
                        ),
                    ))

                for _, element in sorted(page_items, key=lambda t: t[0]):
                    element.order_index = order
                    order += 1
                    elements.append(element)

            bookmarks = [
                {"level": lvl, "title": title, "page": page, "order_index": i}
                for i, (lvl, title, page) in enumerate(doc.get_toc())
            ]

            return ExtractedDocument(
                page_count=page_count,
                has_text_layer=has_text_layer,
                needs_ocr=not has_text_layer,
                elements=elements,
                bookmarks=bookmarks,
            )
        finally:
            doc.close()
