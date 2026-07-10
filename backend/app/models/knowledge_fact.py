from dataclasses import dataclass
from typing import Optional


@dataclass
class KnowledgeFact:
    id: int
    session_id: int
    document_id: Optional[int]
    category: str
    subcategory: str
    value: str
    confidence: float
    evidence: str
    stage: str
    source_document: str
    created_at: str
