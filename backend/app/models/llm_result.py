from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class LLMResult:
    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    latency_ms: int = 0
    status: str = "SUCCESS"
    raw: Dict[str, Any] = field(default_factory=dict)
