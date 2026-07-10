from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.api.schemas import (
    AcquisitionJobOut,
    TTSProviderOut,
    VideoBatchRequest,
    VideoGenerateRequest,
    VideoList,
    VideoOut,
    VideoPreviewRequest,
    VideoSourceOut,
    VideoStats,
    VideoTemplateOut,
)
from app.models.rbac import User
from app.models.video import Video
from app.repositories.acquisition_repository import AcquisitionJobRepository
from app.repositories.user_repository import UserRepository
from app.repositories.video_repository import VideoRepository
from app.services.video_generation_service import VideoGenerationService
from app.shared.security import decode_access_token

router = APIRouter(prefix="/api/videos", tags=["videos"])

MODULE = "videos"


def _video_out(video: Video) -> VideoOut:
    out = VideoOut.model_validate(video)
    out.has_srt = bool(video.srt_path)
    out.has_thumbnail = bool(video.thumbnail_path)
    return out


def _token_user(token: str, db: Session, permission: str) -> User:
    try:
        user_id = int(decode_access_token(token).get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = UserRepository(db).get(user_id)
    if not user or not user.has_permission(permission):
        raise HTTPException(status_code=403, detail="Not permitted")
    return user


@router.get("/stats", response_model=VideoStats)
def stats(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return VideoStats(**VideoRepository(db).stats())


@router.get("/sources", response_model=list[VideoSourceOut])
def sources(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    service = VideoGenerationService(db)
    return [
        VideoSourceOut(
            path=s.path,
            question_count=s.question_count,
            usable_count=s.usable_count,
            topics=s.topics,
        )
        for s in service.sources.list_sources()
    ]


@router.get("/templates", response_model=list[VideoTemplateOut])
def templates(
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return VideoGenerationService.templates()


@router.get("/tts-providers", response_model=list[TTSProviderOut])
def tts_providers(
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    from app.integrations.tts import list_tts_providers

    return list_tts_providers()


@router.post("/generate", response_model=VideoOut)
def generate(
    payload: VideoGenerateRequest,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    try:
        video, _job = VideoGenerationService(db).queue(
            **payload.model_dump(), user_id=user.id
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _video_out(video)


@router.post("/batch", response_model=list[VideoOut])
def generate_batch(
    payload: VideoBatchRequest,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    data = payload.model_dump()
    batch_count = data.pop("batch_count")
    question_count = data.pop("question_count")
    data.pop("offset", None)  # batch computes its own windows
    try:
        videos = VideoGenerationService(db).queue_batch(
            batch_count=batch_count, question_count=question_count, user_id=user.id, **data
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return [_video_out(v) for v in videos]


@router.post("/preview")
def preview(
    payload: VideoPreviewRequest,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    try:
        return VideoGenerationService(db).preview(**payload.model_dump())
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=VideoList)
def list_videos(
    search: str | None = None,
    kind: str | None = None,
    status: str | None = None,
    template: str | None = None,
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    items, total = VideoRepository(db).query(
        search=search, kind=kind, status=status, template=template, limit=limit, offset=offset
    )
    return VideoList(items=[_video_out(v) for v in items], total=total, limit=limit, offset=offset)


@router.get("/jobs", response_model=list[AcquisitionJobOut])
def list_jobs(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return AcquisitionJobRepository(db).list("video")


@router.get("/{video_id}", response_model=VideoOut)
def get_video(
    video_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    video = VideoRepository(db).get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return _video_out(video)


@router.get("/{video_id}/download")
def download(
    video_id: int,
    token: str,
    db: Session = Depends(db_session),
):
    _token_user(token, db, f"{MODULE}:export")
    video = VideoRepository(db).get(video_id)
    if not video or not video.file_path or not Path(video.file_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(
        video.file_path, media_type="video/mp4", filename=Path(video.file_path).name
    )


@router.get("/{video_id}/subtitles")
def subtitles(
    video_id: int,
    token: str,
    db: Session = Depends(db_session),
):
    _token_user(token, db, f"{MODULE}:export")
    video = VideoRepository(db).get(video_id)
    if not video or not video.srt_path or not Path(video.srt_path).exists():
        raise HTTPException(status_code=404, detail="Subtitles not found")
    return FileResponse(
        video.srt_path, media_type="text/plain", filename=Path(video.srt_path).name
    )


@router.get("/{video_id}/thumbnail")
def thumbnail(
    video_id: int,
    token: str,
    db: Session = Depends(db_session),
):
    _token_user(token, db, f"{MODULE}:view")
    video = VideoRepository(db).get(video_id)
    if not video or not video.thumbnail_path or not Path(video.thumbnail_path).exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(video.thumbnail_path, media_type="image/jpeg")


@router.delete("/{video_id}")
def delete_video(
    video_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:delete")),
):
    service = VideoGenerationService(db)
    video = service.repo.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.status == "rendering":
        raise HTTPException(status_code=400, detail="Cannot delete while rendering")
    service.delete(video)
    return {"status": "deleted"}
