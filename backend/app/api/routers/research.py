from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_permission
from app.config.knowledge_config import KnowledgeConfig
from app.services.knowledge_research_service import KnowledgeResearchService
from app.services.llm_service import LLMService
from app.services.source_search_service import SourceSearchService

router = APIRouter(prefix="/api/research", tags=["knowledge-research"])

MODULE = "research"

# Shared instance so all requests use one executor pool and one repository.
_service = KnowledgeResearchService()


class SessionCreateRequest(BaseModel):
    mode: str = Field(pattern="(?i)^(url|topic)$")
    input_value: str = Field(min_length=1, max_length=2000)
    source_count: int = Field(default=5, ge=1, le=20)
    source_type: str = "youtube"
    ai_provider: str = ""
    ai_model: str = ""


@router.get("/providers")
def get_providers(
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return {
        "llm_providers": sorted(LLMService._PROVIDERS.keys()),
        "source_types": sorted(SourceSearchService._PROVIDERS.keys()),
        "default_provider": KnowledgeConfig.llm_provider(),
        "default_model": KnowledgeConfig.default_model(),
    }


@router.post("/sessions", status_code=201)
def create_session(
    request: SessionCreateRequest,
    _: object = Depends(require_permission(f"{MODULE}:execute")),
):
    try:
        session_id = _service.start_session(
            mode=request.mode,
            input_value=request.input_value,
            source_count=request.source_count,
            source_type=request.source_type,
            ai_provider=request.ai_provider,
            ai_model=request.ai_model,
        )
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=400, detail=str(error))

    return {"session_id": session_id}


@router.get("/sessions")
def list_sessions(
    status: str = "",
    topic: str = "",
    date_from: str = "",
    date_to: str = "",
    provider: str = "",
    source_type: str = "",
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return {
        "sessions": _service.list_sessions(
            status=status or None,
            topic=topic or None,
            date_from=date_from or None,
            date_to=date_to or None,
            provider=provider or None,
            source_type=source_type or None,
        )
    }


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    session = _service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.get("/sessions/{session_id}/results")
def get_results(
    session_id: int,
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    results = _service.get_results(session_id)

    if not results:
        raise HTTPException(status_code=404, detail="Session not found")

    return results


@router.get("/sessions/{session_id}/facts")
def get_facts(
    session_id: int,
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    if not _service.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    return {"facts": _service.repo.list_facts_by_session(session_id)}


@router.get("/sessions/{session_id}/entities")
def get_entities(
    session_id: int,
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    if not _service.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    return {"entities": _service.repo.list_entities_by_session(session_id)}


@router.get("/sessions/{session_id}/consensus")
def get_consensus(
    session_id: int,
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    if not _service.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    results = _service.get_results(session_id)

    return {"consensus": results["consensus"]}
