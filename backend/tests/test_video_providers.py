"""Tests for the source-agnostic video provider layer.

These lock in the contract that the ingestion pipeline is source-agnostic: a new
source is added by registering a `VideoProvider`, and the shared worker selects
the downloader and gates the classification stage purely off the provider -- with
no source-string branching in the pipeline itself.
"""
from pathlib import Path

import pytest

from app.integrations import video_providers as vp


def test_live_sources_are_registered():
    assert vp.get_provider("youtube").name == "youtube"
    assert vp.get_provider("instagram").name == "instagram"


def test_classification_policy_is_per_provider():
    # YouTube keeps its original behaviour (no content classification);
    # Instagram classifies. The worker reads this flag, not a source string.
    assert vp.get_provider("youtube").classify_frames is False
    assert vp.get_provider("instagram").classify_frames is True


def test_unknown_source_raises():
    with pytest.raises(ValueError):
        vp.get_provider("does-not-exist")


def test_register_extends_without_pipeline_change():
    """Adding a source (e.g. a local MP4) is a single registration."""

    class LocalFileProvider:
        name = "local_mp4"
        classify_frames = True

        def fetch(self, ref: str, output_dir: Path) -> dict:  # pragma: no cover - not run
            return {"path": ref}

    provider = LocalFileProvider()
    try:
        assert isinstance(provider, vp.VideoProvider)  # structural conformance
        vp.register(provider)
        assert vp.get_provider("local_mp4") is provider
        assert vp.get_provider("local_mp4").classify_frames is True
    finally:
        vp._PROVIDERS.pop("local_mp4", None)


def test_worker_has_no_source_string_branching():
    """The pipeline must not key behaviour off specific source names."""
    worker_src = (Path(__file__).resolve().parents[1] / "app" / "core" / "worker.py").read_text(
        encoding="utf-8"
    )
    assert '"instagram"' not in worker_src
    assert "'instagram'" not in worker_src
    assert 'job.source ==' not in worker_src
