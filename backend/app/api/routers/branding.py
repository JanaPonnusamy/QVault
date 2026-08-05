from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.api.schemas import BrandingConfigOut
from app.services.branding_service import BrandingService

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/branding", response_model=BrandingConfigOut)
def get_branding(
    tenant: str | None = Query(default=None),
    x_qvault_tenant: str | None = Header(default=None),
    db: Session = Depends(db_session),
):
    return BrandingConfigOut(**BrandingService(db).get_branding(tenant or x_qvault_tenant))
