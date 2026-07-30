"""Parses a downloaded GK-website HTML page into structured content (MCQ /
essay / fill-in-the-blank) using the `page_type`/`plugin` metadata
`GkWebsiteProvider.extract_metadata()` attached. PDFs are not parsed here —
they're hand-off to the existing Documents/Knowledge Extraction pipeline
instead (see `GkScraperService._ingest_pdf`), so this only implements the
HTML path of the `DocumentParser` contract.
"""

from __future__ import annotations

from pathlib import Path

from app.integrations.acquisition.dto import AcquisitionDocument
from app.integrations.acquisition.parser import ParsedDocument
from app.integrations.gk_extractors import extract_essay, extract_fill_blank, extract_mcq


class GkWebsiteParser:
    def parse(self, document: AcquisitionDocument) -> ParsedDocument:
        if document.document_type != "html" or not document.local_file:
            return ParsedDocument(source=document, warnings=["not an HTML document; skipped"])

        html = Path(document.local_file).read_text(encoding="utf-8", errors="ignore")
        page_type = document.metadata.get("page_type", "unsupported")
        plugin = document.metadata.get("plugin")
        elements: list[dict] = []
        warnings: list[str] = []

        if page_type == "mcq":
            questions, ai_used = extract_mcq(document.source_url, html, plugin)
            elements = [{"type": "mcq", **q} for q in questions]
            if ai_used:
                warnings.append("AI-assisted extraction used (no known deterministic parser matched)")
        elif page_type == "essay":
            essay = extract_essay(document.source_url, html)
            if essay:
                elements = [{"type": "essay", **essay}]
        elif page_type == "fill_blank":
            items, ai_used = extract_fill_blank(document.source_url, html)
            elements = [{"type": "fill_blank", **i} for i in items]
            if ai_used:
                warnings.append("AI-assisted extraction used for missing answers")
        else:
            warnings.append(f"unsupported page_type: {page_type}")

        return ParsedDocument(source=document, text="", elements=elements, warnings=warnings)
