"""Deterministic on-disk layout for acquired documents:

    storage/acquisition/<provider>/<exam>/<year>/<source_id>/
        original_file
        metadata.json

Providers only download files here — no OCR, no parsing, no question
extraction happens in this layer (that starts in Phase 2B/2C).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from app.config.settings import settings
from app.integrations.acquisition.dto import AcquisitionDocument


class AcquisitionStorage:
    @staticmethod
    def path_for(provider: str, exam: str, year: str | int, source_id: str) -> Path:
        exam_part = exam or "unspecified"
        year_part = str(year) if year else "unspecified"
        return settings.acquisition_dir / provider / exam_part / year_part / source_id

    @staticmethod
    def save(
        document: AcquisitionDocument,
        data: bytes,
        filename: str,
        exam: str = "",
        year: str | int = "",
    ) -> Path:
        target_dir = AcquisitionStorage.path_for(document.provider, exam, year, document.source_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        original_path = target_dir / filename
        original_path.write_bytes(data)

        payload = asdict(document)
        payload["discovered_at"] = document.discovered_at.isoformat()
        payload["local_file"] = str(original_path)
        (target_dir / "metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

        return original_path
