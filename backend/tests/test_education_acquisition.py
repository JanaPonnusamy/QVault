from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.integrations.acquisition.dto import AcquisitionDocument
from app.integrations.acquisition.providers.education.discovery import _is_relevant_search_target, _normalize_search_result_url
from app.integrations.acquisition.providers.education.parser import parse_education_document
from app.repositories.education_repository import EducationRepository
from app.services.education_field_catalog import summarize_document_fields
from app.services.education_acquisition_service import EducationAcquisitionService


def test_html_parser_extracts_and_normalizes_school_form_fields(tmp_path):
    html = """
    <html>
      <head><title>ABC Public School Admission Form 2026</title></head>
      <body>
        <h1>ABC Public School</h1>
        <p>CBSE Affiliation, Tamil Nadu</p>
        <p>Email: admissions@abcschool.edu.in</p>
        <p>Phone: 9876543210</p>
        <form>
          <label for="student_name">Student Name</label>
          <input id="student_name" name="student_name" />
          <label for="dob">Date of Birth</label>
          <input id="dob" name="dob" />
        </form>
      </body>
    </html>
    """
    path = tmp_path / "admission.html"
    path.write_text(html, encoding="utf-8")

    parsed = parse_education_document(
        AcquisitionDocument(
            provider="education_manual_url",
            source_id="1",
            source_url="https://abcschool.edu.in/admission",
            document_type="html",
            local_file=str(path),
            metadata={"source_kind": "manual_url"},
        )
    )

    keys = {field["canonical_key"] for field in parsed.fields}
    assert parsed.classification == "admission_form"
    assert parsed.institution_type == "school"
    assert parsed.board == "CBSE"
    assert parsed.state == "Tamil Nadu"
    assert "student_name" in keys
    assert "dob" in keys
    assert "admission" in parsed.tags


def test_service_exports_normalized_rows(tmp_path, monkeypatch):
    from app.config import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "storage_dir", tmp_path)
    settings_module.settings.education_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    db = Session()
    try:
        repo = EducationRepository(db)
        source = repo.upsert_source(
            source_key="abcschool.edu.in",
            institution_name="ABC Public School",
            institution_type="school",
            board="CBSE",
            state="Tamil Nadu",
            district="Chennai",
            website_url="https://abcschool.edu.in",
            source_kind="website_crawl",
            is_government=False,
            metadata={"board": "CBSE"},
        )
        db.flush()
        repo.replace_document(
            source=source,
            acquisition_item_id=None,
            url="https://abcschool.edu.in/admission",
            title="Admission Form",
            document_type="html",
            classification="admission_form",
            file_type="html",
            checksum="abc",
            local_file=str(tmp_path / "admission.html"),
            language="en",
            summary="Admission form for 2026 intake.",
            metadata={"source_kind": "website_crawl"},
            fields=[
                {"canonical_key": "student_name", "label": "Student Name", "value": "", "source_kind": "form", "confidence": 0.95},
                {"canonical_key": "phone", "label": "Phone", "value": "9876543210", "source_kind": "metadata", "confidence": 0.98},
            ],
            tags=["admission", "cbse"],
        )
        db.commit()

        service = EducationAcquisitionService(db)
        exported = service.export_json()
        csv_text = service.export_csv()
        sqlite_path = service.export_sqlite()

        assert exported["stats"]["documents"] == 1
        assert any(row["classification"] == "admission_form" for row in exported["rows"])
        assert "document_id" in csv_text
        assert sqlite_path.exists()
    finally:
        db.close()


def test_search_result_normalization_decodes_bing_redirect_and_rejects_transfer_sites():
    bing_url = (
        "https://www.bing.com/ck/a?!&&p=token"
        "&u=a1aHR0cHM6Ly9wYXRuYS5uaWMuaW4vZWR1Y2F0aW9uLw"
        "&ntb=1"
    )

    normalized = _normalize_search_result_url(bing_url)

    assert normalized == "https://patna.nic.in/education/"
    assert _is_relevant_search_target(normalized) is True
    assert _is_relevant_search_target("https://www.swisstransfer.com/en") is False
    assert _is_relevant_search_target("https://www.justdial.com/Patna/Schools") is False


def test_field_summary_separates_enquiry_application_and_custom_fields():
    summary = summarize_document_fields(
        [
            {"canonical_key": "phone", "label": "Mobile Number", "value": "9876543210", "source_kind": "form", "confidence": 0.95},
            {"canonical_key": "email", "label": "Email", "value": "parent@example.com", "source_kind": "form", "confidence": 0.95},
            {"canonical_key": "class_to_join", "label": "Class to Join", "value": "Class 6", "source_kind": "form", "confidence": 0.95},
            {"canonical_key": "student_name", "label": "Student Name", "value": "Arun Kumar", "source_kind": "form", "confidence": 0.95},
            {"canonical_key": "sibling_name", "label": "Sibling Name", "value": "Anu", "source_kind": "form", "confidence": 0.8},
        ],
        {"institution_name": "ABC Public School", "phone": "9876543210", "board": "CBSE"},
    )

    assert "phone" not in summary["missing_required_enquiry"]
    assert "email" not in summary["missing_required_enquiry"]
    assert "class_to_join" not in summary["missing_required_enquiry"]
    assert "previous_school" in summary["missing_required_enquiry"]
    assert any(item["key"] == "student_name" and item["present"] for item in summary["application_fields"])
    assert any(item["key"] == "sibling_name" for item in summary["custom_fields"])
    assert any(item["key"] == "institution_name" for item in summary["raw_metadata_fields"])
