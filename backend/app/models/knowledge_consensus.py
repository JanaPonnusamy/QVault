from dataclasses import dataclass


@dataclass
class KnowledgeConsensus:
    id: int
    session_id: int
    common_practices_json: str
    differences_json: str
    conflicting_advice_json: str
    recommendation_json: str
    confidence: float
    created_at: str
