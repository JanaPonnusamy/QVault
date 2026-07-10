from dataclasses import dataclass
from typing import Optional


@dataclass
class KnowledgeSession:
    id: int
    mode: str
    input_value: str
    source_count_requested: int
    source_type: str
    ai_provider: str
    ai_model: str
    status: str
    current_stage: str
    progress: int
    storage_directory: str
    pipeline_version: str
    report_path: Optional[str]
    report_markdown_path: Optional[str]
    error_message: Optional[str]
    created_at: str
    updated_at: str
