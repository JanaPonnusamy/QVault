from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EducationFieldDefinition:
    key: str
    label: str
    stage: str
    required: bool
    description: str


FIELD_DEFINITIONS: tuple[EducationFieldDefinition, ...] = (
    EducationFieldDefinition("student_name", "Student Name", "application", True, "Primary student/applicant name."),
    EducationFieldDefinition("phone", "Mobile Number", "enquiry", True, "Primary parent/student contact number."),
    EducationFieldDefinition("email", "Email", "enquiry", True, "Primary parent/student email address."),
    EducationFieldDefinition("class_to_join", "Class to Join", "enquiry", True, "Requested class/grade for admission."),
    EducationFieldDefinition("previous_school", "Previous School", "enquiry", True, "Last attended school/institution."),
    EducationFieldDefinition("dob", "Date of Birth", "application", True, "Student date of birth."),
    EducationFieldDefinition("gender", "Gender", "application", True, "Student gender."),
    EducationFieldDefinition("father_name", "Father Name", "application", True, "Father or male guardian name."),
    EducationFieldDefinition("mother_name", "Mother Name", "application", True, "Mother or female guardian name."),
    EducationFieldDefinition("guardian_name", "Guardian Name", "application", False, "Guardian name when applicable."),
    EducationFieldDefinition("address", "Address", "application", True, "Residential address."),
    EducationFieldDefinition("aadhaar", "Aadhaar Number", "application", False, "Identity number if collected."),
    EducationFieldDefinition("community", "Category / Community", "application", False, "Reservation/community detail."),
    EducationFieldDefinition("religion", "Religion", "application", False, "Religion if collected by school."),
    EducationFieldDefinition("blood_group", "Blood Group", "application", False, "Medical blood group."),
    EducationFieldDefinition("occupation", "Parent Occupation", "application", False, "Occupation of parent/guardian."),
    EducationFieldDefinition("annual_income", "Annual Income", "application", False, "Family annual income."),
    EducationFieldDefinition("transfer_certificate", "Transfer Certificate", "application", False, "TC number or transfer certificate detail."),
    EducationFieldDefinition("emis", "EMIS Number", "application", False, "Education management ID if applicable."),
    EducationFieldDefinition("transport", "Transport Requirement", "application", False, "Bus/transport option."),
    EducationFieldDefinition("hostel", "Hostel Requirement", "application", False, "Hostel accommodation option."),
    EducationFieldDefinition("emergency_contact", "Emergency Contact", "application", False, "Emergency contact person/number."),
    EducationFieldDefinition("medical_history", "Medical History", "application", False, "Health condition/allergy/medical note."),
)

FIELD_DEFINITION_MAP = {field.key: field for field in FIELD_DEFINITIONS}
ENQUIRY_KEYS = [field.key for field in FIELD_DEFINITIONS if field.stage == "enquiry"]
APPLICATION_KEYS = [field.key for field in FIELD_DEFINITIONS if field.stage == "application"]


def field_catalog_payload() -> dict:
    return {
        "enquiry_fields": [field_payload(field) for field in FIELD_DEFINITIONS if field.stage == "enquiry"],
        "application_fields": [field_payload(field) for field in FIELD_DEFINITIONS if field.stage == "application"],
        "notes": [
            "Enquiry is the quick lead-capture stage before admission form filling.",
            "Application is the fuller admission form stage after the student decides to join.",
            "Any field not in the standard catalog is still preserved as metadata/custom input for later school-specific mapping.",
        ],
    }


def field_payload(field: EducationFieldDefinition) -> dict:
    return {
        "key": field.key,
        "label": field.label,
        "stage": field.stage,
        "required": field.required,
        "description": field.description,
    }


def summarize_document_fields(fields: list[dict], metadata: dict | None = None) -> dict:
    metadata = metadata or {}
    values_by_key: dict[str, list[dict]] = {}
    custom_fields: list[dict] = []
    for field in fields:
        key = str(field.get("canonical_key") or "").strip()
        if not key:
            continue
        if key in FIELD_DEFINITION_MAP:
            values_by_key.setdefault(key, []).append(field)
        else:
            custom_fields.append(
                {
                    "key": key,
                    "label": field.get("label") or key.replace("_", " ").title(),
                    "value": field.get("value") or "",
                    "source_kind": field.get("source_kind") or "metadata",
                }
            )

    matched = []
    missing_enquiry = []
    missing_application = []
    for definition in FIELD_DEFINITIONS:
        row = {
            **field_payload(definition),
            "present": definition.key in values_by_key,
            "values": [
                {
                    "value": item.get("value") or "",
                    "label": item.get("label") or definition.label,
                    "source_kind": item.get("source_kind") or "metadata",
                    "confidence": float(item.get("confidence") or 0.0),
                }
                for item in values_by_key.get(definition.key, [])
            ],
        }
        matched.append(row)
        if definition.stage == "enquiry" and definition.required and not row["present"]:
            missing_enquiry.append(definition.key)
        if definition.stage == "application" and definition.required and not row["present"]:
            missing_application.append(definition.key)

    raw_metadata_fields = []
    for key, value in metadata.items():
        if key in {"source_url", "local_file", "document_type", "source_kind", "emails", "phones"}:
            continue
        if isinstance(value, (str, int, float)) and str(value).strip():
            raw_metadata_fields.append({"key": key, "value": str(value)})

    return {
        "enquiry_fields": [row for row in matched if row["stage"] == "enquiry"],
        "application_fields": [row for row in matched if row["stage"] == "application"],
        "custom_fields": custom_fields,
        "raw_metadata_fields": raw_metadata_fields,
        "missing_required_enquiry": missing_enquiry,
        "missing_required_application": missing_application,
        "supports_custom_fields": True,
    }
