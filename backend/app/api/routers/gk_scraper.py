from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.api.schemas import (
    AcquisitionJobOut,
    GkProfileList,
    GkProfileOut,
    GkScanRequest,
    GkVisitedUrlList,
)
from app.config.settings import settings
from app.models.rbac import User
from app.repositories.acquisition_item_repository import AcquisitionItemRepository
from app.repositories.acquisition_repository import AcquisitionJobRepository
from app.services.gk_scraper_service import GkScraperService

router = APIRouter(prefix="/api/sources/gk-scraper", tags=["gk_scraper"])

MODULE = "gk_scraper"
SOURCE = "gk_scraper"


@router.get("/jobs", response_model=list[AcquisitionJobOut])
def list_jobs(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return AcquisitionJobRepository(db).list(SOURCE)


@router.post("/scan", response_model=AcquisitionJobOut)
def scan(
    payload: GkScanRequest,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    homepage_url = payload.homepage_url.strip()
    if not homepage_url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="homepage_url must start with http:// or https://")
    return GkScraperService(db).start_scan(homepage_url, user.id)


@router.get("/profiles", response_model=GkProfileList)
def list_profiles(
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    if not settings.gk_scraper_dir.exists():
        return GkProfileList(domains=[])
    domains = sorted(
        p.name for p in settings.gk_scraper_dir.iterdir() if p.is_dir() and (p / "profile.md").exists()
    )
    return GkProfileList(domains=domains)


@router.get("/profiles/{domain}", response_model=GkProfileOut)
def get_profile(
    domain: str,
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    path = settings.gk_scraper_dir / domain / "profile.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No profile for this domain yet")
    updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return GkProfileOut(domain=domain, content=path.read_text(encoding="utf-8"), updated_at=updated_at)


@router.get("/profiles/{domain}/urls", response_model=GkVisitedUrlList)
def list_visited_urls(
    domain: str,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    items, total = AcquisitionItemRepository(db).list_by_provider(
        provider=f"gk_{domain}", status=status, limit=min(limit, 200), offset=offset,
    )
    return GkVisitedUrlList(total=total, items=items)
