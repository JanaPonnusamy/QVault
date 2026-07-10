from dataclasses import dataclass
from typing import Optional


@dataclass
class KnowledgeEntity:
    id: int
    session_id: int
    document_id: Optional[int]
    entity_name: str
    entity_type: str
    category: str
    confidence: float
    evidence: str
    created_at: str
