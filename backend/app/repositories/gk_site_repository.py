from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.acquisition import GkSite


class GkSiteRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, active_only: bool = False) -> list[GkSite]:
        stmt = select(GkSite).order_by(GkSite.name)
        if active_only:
            stmt = stmt.where(GkSite.active == True)  # noqa: E712
        return list(self.db.scalars(stmt))

    def find_by_url(self, homepage_url: str) -> GkSite | None:
        return self.db.scalar(select(GkSite).where(GkSite.homepage_url == homepage_url))

    def add(self, site: GkSite, commit: bool = True) -> GkSite:
        self.db.add(site)
        if commit:
            self.db.commit()
            self.db.refresh(site)
        else:
            self.db.flush()
        return site
