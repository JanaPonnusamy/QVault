"""Ordered list of all migrations ever written. Never edit or remove an
existing entry — append new ones. The runner tracks completion by name in
system.database_version, so removing/renaming an entry would cause it to
re-run (or an already-applied one to look pending)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.migrations.runner import Migration
from app.models.acquisition import GkSite
from app.models.mixins import DEFAULT_TENANT_ID
from app.models.system import Tenant


def _seed_default_tenant(db: Session) -> None:
    if db.get(Tenant, DEFAULT_TENANT_ID) is not None:
        return
    db.add(
        Tenant(
            tenant_id=DEFAULT_TENANT_ID,
            tenant_code="default",
            tenant_name="Default Tenant",
            active=True,
        )
    )


TOP_20_GK_SITES = [
    ("GK Today", "https://www.gktoday.in/"),
    ("Examveda", "https://www.examveda.com/"),
    ("Testbook", "https://testbook.com/"),
    ("Jagran Josh", "https://www.jagranjosh.com/"),
    ("BYJU'S GK", "https://byjus.com/"),
    ("IndiaBIX", "https://www.indiabix.com/"),
    ("Adda247 Current Affairs", "https://currentaffairs.adda247.com/"),
    ("Oliveboard", "https://www.oliveboard.in/"),
    ("SSC Adda", "https://www.sscadda.com/"),
    ("Bankers Adda", "https://www.bankersadda.com/"),
    ("Jago Quiz", "https://www.jagoquiz.com/"),
    ("GK Tricks", "https://www.gktricks.in/"),
    ("Affairs Cloud", "https://www.affairscloud.com/"),
    ("GK Series", "https://www.gkseries.com/"),
    ("SuccessCDS", "https://www.successcds.net/"),
    ("ExamPundit", "https://exampundit.in/"),
    ("Free Job Alert", "https://www.freejobalert.com/"),
    ("Government Adda", "https://www.governmentadda.com/"),
    ("Pendulum Edu", "https://pendulumedu.com/"),
    ("GK Planet", "https://www.gkplanet.in/"),
]


def _seed_gk_sites(db: Session) -> None:
    existing = {url for (url,) in db.query(GkSite.homepage_url).all()}
    for name, url in TOP_20_GK_SITES:
        if url in existing:
            continue
        db.add(GkSite(name=name, homepage_url=url))


MIGRATIONS: list[Migration] = [
    Migration(
        name="0001_seed_default_tenant",
        description="Seed the single default tenant referenced by TenantAuditMixin.tenant_id.",
        fn=_seed_default_tenant,
    ),
    Migration(
        name="0002_seed_gk_sites",
        description="Seed the top 20 Indian competitive-exam GK/current-affairs sites into gk_sites.",
        fn=_seed_gk_sites,
    ),
]
