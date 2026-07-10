from dataclasses import dataclass
from typing import Optional


@dataclass
class KnowledgeDocument:
    id: int
    session_id: int
    document_type: str
    source_reference: str
    title: str
    url: str
    language: str
    duration: int
    word_count: int
    character_count: int
    file_size: int
    checksum: str
    processing_version: str
    transcript_path: Optional[str]
    subtitle_path: Optional[str]
    ocr_path: Optional[str]
    merged_text_path: Optional[str]
    summary_path: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: str
    updated_at: str
