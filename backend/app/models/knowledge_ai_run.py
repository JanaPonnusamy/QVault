from dataclasses import dataclass
from typing import Optional


@dataclass
class KnowledgeAiRun:
    id: int
    session_id: int
    document_id: Optional[int]
    stage: str
    provider: str
    model: str
    prompt_name: str
    prompt_version: str
    system_prompt_hash: str
    user_prompt_hash: str
    temperature: float
    max_tokens: int
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    latency_ms: int
    status: str
    created_at: str
