from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.integrations.acquisition.dto import AcquisitionDocument
from app.integrations.acquisition.providers.education.parser import parse_education_document
from app.repositories.education_repository import EducationRepository
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
