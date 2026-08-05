from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.system import ApplicationSetting, Tenant


DEFAULT_BRANDING = {
    "tenant_code": "default",
    "tenant_name": "Default Tenant",
    "business_name": settings.app_name,
    "app_name": f"{settings.app_name} Admin",
    "tagline": "Exam Intelligence Platform",
    "logo_text": settings.app_name,
    "logo_icon": "bi-shield-lock-fill",
    "logo_url": "",
    "fonts": {
        "base": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        "heading": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        "mono": "ui-monospace, SFMono-Regular, Consolas, monospace",
    },
    "theme": {
        "background": "#f4f6fa",
        "surface": "#ffffff",
        "surface_alt": "#f8fafc",
        "text": "#1e293b",
        "muted_text": "#64748b",
        "sidebar_background": "#0f172a",
        "sidebar_text": "#cbd5e1",
        "sidebar_group_text": "#64748b",
        "accent": "#2563eb",
        "accent_contrast": "#ffffff",
        "border": "#e2e8f0",
        "login_background": "linear-gradient(135deg,#0f172a,#1e3a8a)",
    },
    "module_colors": {},
}


class BrandingService:
    def __init__(self, db: Session):
        self.db = db

    def get_branding(self, tenant_code: str | None = None) -> dict:
        config = self._load_branding_file()
        resolved_tenant = tenant_code or config.get("default_tenant_code") or "default"
        tenant_branding = config.get("tenants", {}).get(resolved_tenant, {})
        merged = _deep_merge(deepcopy(DEFAULT_BRANDING), tenant_branding)

        tenant = self.db.scalar(select(Tenant).where(Tenant.tenant_code == resolved_tenant))
        if tenant is not None:
            merged["tenant_code"] = tenant.tenant_code
            merged["tenant_name"] = tenant.tenant_name

        override = self.db.scalar(
            select(ApplicationSetting).where(ApplicationSetting.key == f"branding.{resolved_tenant}")
        )
        if override and override.value.strip():
            try:
                merged = _deep_merge(merged, json.loads(override.value))
            except json.JSONDecodeError:
                pass

        return merged

    def _load_branding_file(self) -> dict:
        path = Path(settings.branding_config_path)
        if not path.exists():
            return {"default_tenant_code": "default", "tenants": {"default": deepcopy(DEFAULT_BRANDING)}}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"default_tenant_code": "default", "tenants": {"default": deepcopy(DEFAULT_BRANDING)}}


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
