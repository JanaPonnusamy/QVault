from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.models.system import ApplicationSetting, Tenant
from app.services.branding_service import BrandingService


def test_branding_service_reads_tenant_config_and_db_override(tmp_path, monkeypatch):
    from app.config import settings as settings_module

    branding_path = tmp_path / "branding.json"
    branding_path.write_text(
        json.dumps(
            {
                "default_tenant_code": "school-a",
                "tenants": {
                    "school-a": {
                        "tenant_code": "school-a",
                        "tenant_name": "School A",
                        "business_name": "School A ERP",
                        "app_name": "School A Admin",
                        "tagline": "Admissions and ERP",
                        "logo_text": "School A",
                        "logo_icon": "bi-building",
                        "logo_url": "",
                        "fonts": {
                            "base": "Lato, sans-serif",
                            "heading": "Merriweather, serif",
                            "mono": "Consolas, monospace",
                        },
                        "theme": {
                            "background": "#ffffff",
                            "surface": "#f9fafb",
                            "surface_alt": "#f3f4f6",
                            "text": "#111827",
                            "muted_text": "#6b7280",
                            "sidebar_background": "#1f2937",
                            "sidebar_text": "#f9fafb",
                            "sidebar_group_text": "#d1d5db",
                            "accent": "#0f766e",
                            "accent_contrast": "#ffffff",
                            "border": "#e5e7eb",
                            "login_background": "linear-gradient(135deg,#1f2937,#0f766e)",
                        },
                        "module_colors": {
                            "education_acquisition": "#0f766e",
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_module.settings, "branding_config_path", branding_path)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    db = Session()
    try:
        db.add(Tenant(tenant_code="school-a", tenant_name="School A Tenant", active=True))
        db.add(
            ApplicationSetting(
                key="branding.school-a",
                value=json.dumps(
                    {
                        "app_name": "School A Custom Admin",
                        "theme": {"accent": "#7c3aed"},
                        "module_colors": {"dashboard": "#7c3aed"},
                    }
                ),
            )
        )
        db.commit()

        branding = BrandingService(db).get_branding("school-a")

        assert branding["tenant_code"] == "school-a"
        assert branding["tenant_name"] == "School A Tenant"
        assert branding["app_name"] == "School A Custom Admin"
        assert branding["theme"]["accent"] == "#7c3aed"
        assert branding["module_colors"]["dashboard"] == "#7c3aed"
        assert branding["module_colors"]["education_acquisition"] == "#0f766e"
    finally:
        db.close()
