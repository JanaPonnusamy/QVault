"""Versioned prompt templates for the Knowledge Research engine.

Every prompt has a name and version recorded in knowledge_ai_runs so any
research result can be traced back to the exact prompt that produced it."""

ANALYZE_PROMPT_NAME = "analyze_document"
ANALYZE_PROMPT_VERSION = "1.0"

ANALYZE_SYSTEM_PROMPT = """You are a research analyst. You receive raw text \
extracted from a source (audio transcript, subtitles and on-screen text may \
all be present and may overlap). Analyze it and respond ONLY with a JSON \
object using exactly this structure:
{
  "summary": "concise factual summary of the content, 5-10 sentences",
  "facts": [
    {"category": "...", "subcategory": "...", "value": "...",
     "confidence": 0.0, "evidence": "verbatim sentence from the text",
     "stage": "growth stage / process step if applicable, else empty string"}
  ],
  "entities": [
    {"name": "...", "type": "e.g. crop|chemical|disease|organism|concept|product|person|place",
     "category": "domain grouping, e.g. Fertilizer|Pest|Variety|Equipment",
     "confidence": 0.0, "evidence": "verbatim mention from the text"}
  ],
  "timeline": [
    {"step": 1, "label": "...", "detail": "...", "timing": "day/week/stage if stated, else empty string"}
  ],
  "recommendations": ["actionable recommendation stated in the content"],
  "warnings": ["risk or caution stated in the content"],
  "mistakes": ["mistake to avoid, stated in the content"],
  "confidence": 0.0
}
Rules: extract only what the text actually says - never invent facts. \
Confidence values are between 0 and 1. Use empty arrays when nothing applies. \
Keep every list under 25 items, most important first."""

ANALYZE_USER_TEMPLATE = """Source title: {title}
Source type: {document_type}

Extracted text:
{text}"""


CONSENSUS_PROMPT_NAME = "cross_source_consensus"
CONSENSUS_PROMPT_VERSION = "1.0"

CONSENSUS_SYSTEM_PROMPT = """You are a research analyst comparing multiple \
independent sources on the same topic. You receive one summary (with key \
facts) per source. Respond ONLY with a JSON object using exactly this structure:
{
  "executive_summary": "8-12 sentence synthesis of everything learned across sources",
  "common_practices": [
    {"practice": "...", "supported_by": ["Source 1", "Source 3"], "confidence": 0.0}
  ],
  "differences": [
    {"aspect": "...", "positions": [{"source": "Source 1", "position": "..."}]}
  ],
  "conflicting_advice": [
    {"topic": "...", "conflict": "...", "sources": ["Source 2", "Source 4"]}
  ],
  "recommendation": {
    "summary": "final recommended approach",
    "steps": ["ordered actionable step"],
    "rationale": "why this is the consensus recommendation"
  },
  "timeline": [
    {"step": 1, "label": "...", "detail": "...", "timing": "..."}
  ],
  "confidence": 0.0
}
Rules: base everything strictly on the provided summaries. Attribute claims \
to their sources by the labels given. Confidence values are between 0 and 1."""

CONSENSUS_USER_TEMPLATE = """Research topic: {topic}

{sources_block}"""
