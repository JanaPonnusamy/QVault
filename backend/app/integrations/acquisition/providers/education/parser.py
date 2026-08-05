from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from app.integrations.acquisition.dto import AcquisitionDocument
from app.integrations.ocr import OCR
from app.integrations.pdf_extractor import PdfExtractor
from app.services.llm_service import LLMService

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+91[-\s]?)?[6-9]\d{9}")
DATE_RE = re.compile(r"\b(?:\d{1,2}[/-]){2}\d{2,4}\b")

FIELD_ALIASES = {
    "student_name": ["student name", "pupil name", "child name", "applicant name", "name of student"],
    "dob": ["dob", "date of birth", "birth date"],
    "gender": ["gender", "sex"],
    "religion": ["religion"],
    "community": ["community", "category", "caste"],
    "blood_group": ["blood group"],
    "mother_name": ["mother name", "name of mother"],
    "father_name": ["father name", "name of father"],
    "guardian_name": ["guardian", "guardian name"],
    "occupation": ["occupation", "parent occupation"],
    "annual_income": ["annual income", "family income"],
    "address": ["address", "residential address"],
    "phone": ["phone", "mobile", "contact number"],
    "email": ["email", "e-mail"],
    "previous_school": ["previous school"],
    "transfer_certificate": ["transfer certificate", "tc number"],
    "aadhaar": ["aadhaar", "aadhar"],
    "emis": ["emis", "emis number"],
    "transport": ["transport", "transport route"],
    "hostel": ["hostel", "hostel required"],
    "emergency_contact": ["emergency contact"],
    "medical_history": ["medical history", "medical information"],
}
GENERIC_FORM_LABELS = {"search", "search here", "keyword", "query", "site search"}

CLASSIFICATION_KEYWORDS = {
    "admission_form": ["admission form", "application form", "apply now", "registration form"],
    "prospectus": ["prospectus", "brochure"],
    "calendar": ["academic calendar", "calendar"],
    "fee_structure": ["fee structure", "fees", "tuition fee"],
    "scholarship": ["scholarship", "scholarships"],
    "policy": ["policy", "code of conduct", "attendance policy", "handbook"],
    "circular": ["circular", "notification", "notice"],
    "transport_form": ["transport form", "bus form"],
    "hostel_form": ["hostel form", "hostel application"],
    "leave_form": ["leave form", "leave application"],
    "medical_form": ["medical form", "medical certificate"],
    "exam_rule": ["examination rules", "exam rules", "assessment policy"],
}

BOARD_KEYWORDS = {
    "CBSE": ["cbse", "central board of secondary education"],
    "ICSE": ["icse", "cisce", "council for the indian school certificate examinations"],
    "State Board": ["state board", "samacheer", "ssc board", "higher secondary education"],
    "University": ["ugc", "autonomous university", "deemed university"],
}

STATE_KEYWORDS = [
    "Tamil Nadu", "Kerala", "Karnataka", "Andhra Pradesh", "Telangana", "Maharashtra", "Delhi",
    "Uttar Pradesh", "Rajasthan", "Gujarat", "West Bengal", "Punjab", "Haryana", "Odisha", "Bihar",
]


@dataclass
class EducationParsedDocument:
    title: str = ""
    document_type: str = ""
    classification: str = "general"
    summary: str = ""
    source_key: str = ""
    institution_name: str = ""
    institution_type: str = ""
    board: str = ""
    state: str = ""
    district: str = ""
    is_government: bool = False
    metadata: dict = field(default_factory=dict)
    fields: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_education_document(document: AcquisitionDocument) -> EducationParsedDocument:
    parser = {
        "html": _parse_html,
        "pdf": _parse_pdf,
        "docx": _parse_docx,
        "image": _parse_image,
        "xml": _parse_xml,
        "txt": _parse_txt,
        "zip": _parse_zip,
    }.get(document.document_type, _parse_txt)
    parsed = parser(document)
    parsed.document_type = document.document_type
    parsed.source_key = _source_key(document.source_url)
    parsed.metadata.setdefault("source_url", document.source_url)
    parsed.metadata.setdefault("local_file", document.local_file or "")
    parsed.metadata.setdefault("document_type", document.document_type)
    parsed.tags = sorted(set(parsed.tags + _tags_from(parsed)))
    return parsed


def _parse_html(document: AcquisitionDocument) -> EducationParsedDocument:
    text = Path(document.local_file or "").read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(text, "html.parser")
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    page_text = soup.get_text("\n", strip=True)
    signal_text = _signal_text(page_text)
    meta = _extract_basic_metadata(signal_text)
    institution_name = meta.get("institution_name") or _first_non_empty(
        title,
        _text_of(soup.find("h1")),
        _text_of(soup.find("meta", attrs={"property": "og:site_name"}), "content"),
    )
    form_fields = _extract_html_form_fields(soup)
    table_fields = _extract_table_fields(soup)
    classification = _classify_document(title + "\n" + signal_text)
    source_kind = document.metadata.get("source_kind") or document.metadata.get("origin", "website")
    board = _board_from(title, signal_text)
    institution_type = _institution_type_from(title, signal_text, document.source_url, board)
    return EducationParsedDocument(
        title=title or institution_name or document.source_url,
        classification=classification,
        summary=_summarize_text(signal_text),
        institution_name=institution_name,
        institution_type=institution_type,
        board=board,
        state=_state_from(signal_text),
        district="",
        is_government=".gov.in" in document.source_url or "government" in signal_text.lower(),
        metadata={**meta, "source_kind": source_kind},
        fields=_merge_fields(meta, form_fields, table_fields),
        tags=[classification, source_kind, *_tag_words(title, signal_text, institution_type, board)],
    )


def _parse_pdf(document: AcquisitionDocument) -> EducationParsedDocument:
    extracted = PdfExtractor.extract(document.local_file or "")
    parts: list[str] = []
    for element in extracted.elements:
        if element.text:
            parts.append(element.text)
        elif element.element_type == "table" and element.extra and element.extra.get("rows"):
            for row in element.extra["rows"]:
                parts.append(" | ".join(str(cell or "").strip() for cell in row))
    text = "\n".join(parts)
    signal_text = _signal_text(text)
    meta = _extract_basic_metadata(signal_text)
    if extracted.needs_ocr:
        meta["needs_ocr"] = "true"
    board = _board_from("", signal_text)
    institution_type = _institution_type_from("", signal_text, document.source_url, board)
    return EducationParsedDocument(
        title=Path(document.local_file or document.source_url).name,
        classification=_classify_document(signal_text),
        summary=_summarize_text(signal_text),
        institution_name=meta.get("institution_name", ""),
        institution_type=institution_type,
        board=board,
        state=_state_from(signal_text),
        district="",
        is_government=".gov.in" in document.source_url or "government" in signal_text.lower(),
        metadata=meta,
        fields=_merge_fields(meta, _extract_line_fields(signal_text), _extract_table_like_fields(signal_text)),
        tags=_tag_words(Path(document.local_file or document.source_url).name, signal_text, institution_type, board),
        warnings=["needs_ocr"] if extracted.needs_ocr else [],
    )


def _parse_docx(document: AcquisitionDocument) -> EducationParsedDocument:
    text_parts: list[str] = []
    try:
        with zipfile.ZipFile(document.local_file or "") as archive:
            xml = archive.read("word/document.xml")
        root = ET.fromstring(xml)
        for node in root.iter():
            if node.tag.endswith("}t") and node.text:
                text_parts.append(node.text)
    except Exception:
        text_parts.append("")
    text = "\n".join(text_parts)
    signal_text = _signal_text(text)
    meta = _extract_basic_metadata(signal_text)
    board = _board_from("", signal_text)
    institution_type = _institution_type_from("", signal_text, document.source_url, board)
    return EducationParsedDocument(
        title=Path(document.local_file or document.source_url).name,
        classification=_classify_document(signal_text),
        summary=_summarize_text(signal_text),
        institution_name=meta.get("institution_name", ""),
        institution_type=institution_type,
        board=board,
        state=_state_from(signal_text),
        district="",
        is_government=".gov.in" in document.source_url or "government" in signal_text.lower(),
        metadata=meta,
        fields=_merge_fields(meta, _extract_line_fields(signal_text)),
        tags=_tag_words(Path(document.local_file or document.source_url).name, signal_text, institution_type, board),
    )


def _parse_image(document: AcquisitionDocument) -> EducationParsedDocument:
    text, confidence = OCR.read_image_detailed(document.local_file or "")
    signal_text = _signal_text(text)
    meta = _extract_basic_metadata(signal_text)
    fields = _merge_fields(meta, _extract_line_fields(signal_text))
    if confidence < 0.6 and text.strip():
        fields.extend(_llm_form_fields(signal_text))
    board = _board_from("", signal_text)
    institution_type = _institution_type_from("", signal_text, document.source_url, board)
    return EducationParsedDocument(
        title=Path(document.local_file or document.source_url).name,
        classification=_classify_document(signal_text),
        summary=_summarize_text(signal_text),
        institution_name=meta.get("institution_name", ""),
        institution_type=institution_type,
        board=board,
        state=_state_from(signal_text),
        district="",
        is_government=".gov.in" in document.source_url or "government" in signal_text.lower(),
        metadata={**meta, "ocr_confidence": confidence},
        fields=fields,
        tags=_tag_words(Path(document.local_file or document.source_url).name, signal_text, institution_type, board),
    )


def _parse_xml(document: AcquisitionDocument) -> EducationParsedDocument:
    text = Path(document.local_file or "").read_text(encoding="utf-8", errors="ignore")
    return _parse_txt(AcquisitionDocument(**{**document.__dict__, "local_file": document.local_file, "document_type": "txt", "metadata": {**document.metadata, "xml": "true"}}))


def _parse_txt(document: AcquisitionDocument) -> EducationParsedDocument:
    text = Path(document.local_file or "").read_text(encoding="utf-8", errors="ignore")
    signal_text = _signal_text(text)
    meta = _extract_basic_metadata(signal_text)
    board = _board_from("", signal_text)
    institution_type = _institution_type_from("", signal_text, document.source_url, board)
    return EducationParsedDocument(
        title=Path(document.local_file or document.source_url).name,
        classification=_classify_document(signal_text),
        summary=_summarize_text(signal_text),
        institution_name=meta.get("institution_name", ""),
        institution_type=institution_type,
        board=board,
        state=_state_from(signal_text),
        district="",
        is_government=".gov.in" in document.source_url or "government" in signal_text.lower(),
        metadata=meta,
        fields=_merge_fields(meta, _extract_line_fields(signal_text)),
        tags=_tag_words(Path(document.local_file or document.source_url).name, signal_text, institution_type, board),
    )


def _parse_zip(document: AcquisitionDocument) -> EducationParsedDocument:
    return EducationParsedDocument(
        title=Path(document.local_file or document.source_url).name,
        classification="archive",
        summary="Archive downloaded for later inspection.",
        metadata={"archive": "true"},
        tags=["archive"],
        warnings=["archive_not_parsed"],
    )


def _extract_basic_metadata(text: str) -> dict:
    lines = [_clean_line(line) for line in text.splitlines() if _clean_line(line)]
    emails = EMAIL_RE.findall(text)
    phones = PHONE_RE.findall(text)
    metadata = {
        "emails": sorted(set(emails)),
        "phones": sorted(set(phones)),
    }
    if lines:
        metadata["institution_name"] = lines[0][:300]
    if emails:
        metadata["email"] = emails[0]
    if phones:
        metadata["phone"] = phones[0]
    return metadata


def _extract_html_form_fields(soup: BeautifulSoup) -> list[dict]:
    fields: list[dict] = []
    for form in soup.find_all("form"):
        for index, control in enumerate(form.find_all(["input", "select", "textarea"])):
            name = (control.get("name") or control.get("id") or "").strip()
            label = _label_for(control, soup) or name
            canonical = _canonicalize_field(label or name)
            if not canonical:
                continue
            if canonical == "search" or _is_generic_field(label, name):
                continue
            fields.append({
                "canonical_key": canonical,
                "label": label,
                "value": control.get("value") or control.get("placeholder") or "",
                "value_type": control.name,
                "source_kind": "form",
                "confidence": 0.95,
                "order_index": index,
            })
    return fields


def _extract_table_fields(soup: BeautifulSoup) -> list[dict]:
    fields: list[dict] = []
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cols = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            if len(cols) < 2:
                continue
            label, value = cols[0], " | ".join(cols[1:])
            canonical = _canonicalize_field(label)
            if canonical:
                fields.append({
                    "canonical_key": canonical,
                    "label": label,
                    "value": value,
                    "value_type": "table",
                    "source_kind": "table",
                    "confidence": 0.85,
                })
    return fields


def _extract_line_fields(text: str) -> list[dict]:
    fields: list[dict] = []
    for line in text.splitlines():
        if ":" not in line:
            continue
        label, value = [part.strip() for part in line.split(":", 1)]
        canonical = _canonicalize_field(label)
        if canonical and value:
            fields.append({
                "canonical_key": canonical,
                "label": label,
                "value": value,
                "value_type": "text",
                "source_kind": "line",
                "confidence": 0.8,
            })
    return fields


def _extract_table_like_fields(text: str) -> list[dict]:
    fields: list[dict] = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        cols = [part.strip() for part in line.split("|") if part.strip()]
        if len(cols) < 2:
            continue
        canonical = _canonicalize_field(cols[0])
        if canonical:
            fields.append({
                "canonical_key": canonical,
                "label": cols[0],
                "value": " | ".join(cols[1:]),
                "value_type": "table",
                "source_kind": "table",
                "confidence": 0.75,
            })
    return fields


def _llm_form_fields(text: str) -> list[dict]:
    if not text.strip():
        return []
    prompt = (
        "Extract only explicit education-form fields from the text. "
        "Return JSON with a top-level 'fields' array of objects: "
        "{canonical_key,label,value}. Do not invent missing values."
    )
    try:
        parsed, _ = LLMService().generate_json(prompt, text[:12000])
    except Exception:
        return []
    rows = parsed.get("fields") if isinstance(parsed, dict) else []
    out: list[dict] = []
    for row in rows or []:
        canonical = _canonicalize_field(str(row.get("canonical_key") or row.get("label") or ""))
        if canonical:
            out.append({
                "canonical_key": canonical,
                "label": str(row.get("label") or canonical),
                "value": str(row.get("value") or ""),
                "value_type": "text",
                "source_kind": "ai",
                "confidence": 0.55,
            })
    return out


def _merge_fields(metadata: dict, *field_groups: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    if metadata.get("phone"):
        merged[("phone", metadata["phone"])] = {
            "canonical_key": "phone", "label": "Phone", "value": metadata["phone"],
            "value_type": "text", "source_kind": "metadata", "confidence": 0.98,
        }
    if metadata.get("email"):
        merged[("email", metadata["email"])] = {
            "canonical_key": "email", "label": "Email", "value": metadata["email"],
            "value_type": "text", "source_kind": "metadata", "confidence": 0.98,
        }
    for group in field_groups:
        for field in group:
            canonical = (field.get("canonical_key") or "").strip()
            value = (field.get("value") or "").strip()
            source_kind = (field.get("source_kind") or "").strip()
            key = (canonical, value or (field.get("label") or "").strip())
            if not canonical:
                continue
            if not value and source_kind != "form":
                continue
            if key not in merged or float(field.get("confidence") or 0) > float(merged[key].get("confidence") or 0):
                merged[key] = field
    return list(merged.values())


def _canonicalize_field(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", label.lower()).strip()
    for canonical, aliases in FIELD_ALIASES.items():
        if normalized == canonical.replace("_", " ") or normalized in aliases:
            return canonical
    if normalized:
        return normalized.replace(" ", "_")
    return ""


def _classify_document(text: str) -> str:
    lowered = text.lower()
    if "direct admission" in lowered or "admission of students" in lowered:
        return "admission_policy"
    for key, phrases in CLASSIFICATION_KEYWORDS.items():
        if any(phrase in lowered for phrase in phrases):
            return key
    return "general"


def _institution_type_from(title: str, text: str, url: str, board: str = "") -> str:
    lowered = f"{title} {text} {url}".lower()
    if ".gov.in" in lowered or "district " in lowered or "government of " in lowered or "education department" in lowered:
        return "government_portal"
    if "university" in lowered:
        return "university"
    if "college" in lowered or "institute" in lowered:
        return "college"
    if "school" in lowered:
        return "school"
    if board in {"CBSE", "ICSE", "State Board"} or "board of secondary education" in lowered:
        return "board"
    return "education"


def _board_from(title: str, text: str) -> str:
    title_lowered = title.lower()
    text_lowered = text.lower()
    matches: list[str] = []
    for board, phrases in BOARD_KEYWORDS.items():
        if any(phrase in title_lowered for phrase in phrases):
            return board
        if any(phrase in text_lowered for phrase in phrases):
            matches.append(board)
    if len(set(matches)) == 1:
        return matches[0]
    return ""


def _state_from(text: str) -> str:
    lowered = text.lower()
    for state in STATE_KEYWORDS:
        if state.lower() in lowered:
            return state
    return ""


def _summarize_text(text: str, limit: int = 400) -> str:
    compact = " ".join(text.split())
    return compact[:limit]


def _source_key(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/").split("/")
    return (parsed.netloc + ("/" + path[0] if path and path[0] else "")).lower()


def _tag_words(title: str, text: str, institution_type: str, board: str) -> list[str]:
    lowered = f"{title} {text}".lower()
    tags = []
    for candidate in (
        "admission", "fee", "hostel", "transport", "cbse", "icse", "state_board",
        "primary", "secondary", "higher_secondary", "engineering", "medical",
        "arts", "commerce", "government", "private", "calendar", "scholarship",
    ):
        if candidate.replace("_", " ") in lowered:
            tags.append(candidate)
    filtered = []
    for tag in tags:
        if institution_type == "government_portal" and tag in {"arts", "commerce", "engineering", "medical", "private"}:
            continue
        if not board and tag in {"cbse", "icse", "state_board"}:
            continue
        filtered.append(tag)
    return filtered


def _tags_from(parsed: EducationParsedDocument) -> list[str]:
    tags = []
    if parsed.institution_type:
        tags.append(parsed.institution_type)
    if parsed.board:
        tags.append(parsed.board.lower().replace(" ", "_"))
    if parsed.state:
        tags.append(parsed.state.lower().replace(" ", "_"))
    if parsed.is_government:
        tags.append("government")
    return tags


def _label_for(control, soup: BeautifulSoup) -> str:
    control_id = control.get("id")
    if control_id:
        label = soup.find("label", attrs={"for": control_id})
        if label:
            return label.get_text(" ", strip=True)
    parent = control.find_parent("label")
    if parent:
        return parent.get_text(" ", strip=True)
    prev = control.find_previous(["label", "th", "td", "span"])
    if prev:
        return prev.get_text(" ", strip=True)
    return ""


def _text_of(node, attr: str | None = None) -> str:
    if not node:
        return ""
    if attr:
        return str(node.get(attr) or "").strip()
    return node.get_text(" ", strip=True)


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _signal_text(text: str, line_limit: int = 120) -> str:
    cleaned = [_clean_line(line) for line in text.splitlines()]
    useful: list[str] = []
    for line in cleaned:
        if not line:
            continue
        lowered = line.lower()
        if lowered in {"search", "search here...", "site map", "social media links", "accessibility links"}:
            continue
        if "click here if the page does not redirect automatically" in lowered:
            continue
        useful.append(line)
        if len(useful) >= line_limit:
            break
    return "\n".join(useful)


def _clean_line(value: str) -> str:
    return value.replace("\ufeff", "").strip()


def _is_generic_field(label: str, name: str) -> bool:
    combined = re.sub(r"[^a-z0-9 ]+", " ", f"{label} {name}".lower()).strip()
    if combined in GENERIC_FORM_LABELS:
        return True
    parts = [part for part in combined.split() if part]
    return bool(parts) and all(part in {"search", "site", "query", "keyword", "find"} for part in parts)
