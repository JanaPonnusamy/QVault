import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_permission
from app.config.knowledge_config import PROVIDER_SPECS, KnowledgeConfig
from app.services.knowledge_research_service import KnowledgeResearchService
from app.services.llm_service import LLMService
from app.services.source_search_service import SourceSearchService

router = APIRouter(prefix="/api/research", tags=["knowledge-research"])

MODULE = "research"

# Shared instance so all requests use one executor pool and one repository.
_service = KnowledgeResearchService()

# Provider model lists change rarely; cache them briefly so the UI can reload
# the dropdown without hitting the provider on every visit.
_MODELS_CACHE_TTL_SECONDS = 600
_models_cache: dict = {}


class SessionCreateRequest(BaseModel):
    mode: str = Field(pattern="(?i)^(url|topic)$")
    input_value: str = Field(min_length=1, max_length=2000)
    source_count: int = Field(default=5, ge=1, le=20)
    source_type: str = "youtube"
    ai_provider: str = ""
    ai_model: str = ""
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, ge=256, le=16000)


@router.get("/providers")
def get_providers(
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return {
        # Rich provider info: name, label, configured flag (never the key
        # itself) and the configured default model, if any.
        "providers": [
            {
                "name": name,
                "label": PROVIDER_SPECS[name]["label"],
                "configured": KnowledgeConfig.provider_configured(name),
                "requires_key": PROVIDER_SPECS[name]["requires_key"],
                "key_env": PROVIDER_SPECS[name]["key_env"],
                "default_model": KnowledgeConfig.provider_default_model(name),
            }
            for name in LLMService._PROVIDERS
        ],
        "source_types": sorted(SourceSearchService._PROVIDERS.keys()),
        "default_provider": KnowledgeConfig.llm_provider(),
        "default_model": KnowledgeConfig.default_model(),
        "default_temperature": 0.2,
        "default_max_tokens": 4000,
        # Legacy shape, kept so existing consumers keep working.
        "llm_providers": sorted(LLMService._PROVIDERS.keys()),
    }


@router.get("/providers/{provider}/models")
def get_provider_models(
    provider: str,
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    if provider not in LLMService._PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")

    cached = _models_cache.get(provider)

    if cached and time.time() - cached[0] < _MODELS_CACHE_TTL_SECONDS:
        return {"models": cached[1]}

    try:
        models = LLMService(provider=provider).list_models()
    except Exception as error:  # noqa: BLE001 - surfaced as a clean 400
        raise HTTPException(status_code=400, detail=str(error))

    _models_cache[provider] = (time.time(), models)

    return {"models": models}


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
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=400, detail=str(error))

    return {"session_id": session_id}


@router.post("/sessions/{session_id}/cancel")
def cancel_session(
    session_id: int,
    _: object = Depends(require_permission(f"{MODULE}:execute")),
):
    if not _service.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    session = _service.cancel_session(session_id)

    if not session:
        raise HTTPException(
            status_code=409, detail="Session already finished"
        )

    return session


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    _: object = Depends(require_permission(f"{MODULE}:execute")),
):
    try:
        deleted = _service.delete_session(session_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"deleted": session_id}


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
