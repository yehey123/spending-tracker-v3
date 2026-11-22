"""Plugin registry: entry-point discovery, skipping, and missing-plugin behaviour."""

import importlib.metadata
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.domain.services.categorizer import _has_ai_credentials, categorizer_service
from src.domain.services.ocr.base import AIPackagesMissing
from src.domain.services.statement_pipeline import _resolve_ocr
from src.plugins import registry
from tests.plugin_fakes import FakeCategorizer, FakeEntryPoint, fake_descriptor


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.reset_cache()
    yield
    registry.reset_cache()


def _patch_eps(monkeypatch, groups: dict):
    def fake_entry_points(group=None, **_):
        return groups.get(group, [])
    monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)


def test_tesseract_builtin_without_plugins(monkeypatch):
    _patch_eps(monkeypatch, {})
    assert list(registry.available()) == ["tesseract"]
    assert registry.get_ocr("tesseract").credit_weight == 0


def test_fake_entry_point_registers_descriptor(monkeypatch):
    desc = fake_descriptor("fakeai")
    _patch_eps(monkeypatch, {registry.OCR_GROUP: [FakeEntryPoint("fakeai", desc)]})
    assert set(registry.available()) == {"tesseract", "fakeai"}
    got = registry.get_ocr("fakeai")
    assert got is desc
    provider = got.build(SimpleNamespace(), registry.make_context(SimpleNamespace()))
    assert provider.built_for == "fakeai"


def test_broken_plugin_is_skipped(monkeypatch):
    good = fake_descriptor("good")
    _patch_eps(monkeypatch, {registry.OCR_GROUP: [
        FakeEntryPoint("broken", exc=ImportError("boom")),
        FakeEntryPoint("good", good),
    ]})
    assert set(registry.available()) == {"tesseract", "good"}


def test_api_version_mismatch_is_skipped(monkeypatch):
    _patch_eps(monkeypatch, {registry.OCR_GROUP: [
        FakeEntryPoint("old", fake_descriptor("old", api_version=999)),
    ]})
    assert list(registry.available()) == ["tesseract"]


def test_non_conforming_plugin_is_skipped(monkeypatch):
    _patch_eps(monkeypatch, {registry.OCR_GROUP: [FakeEntryPoint("junk", object())]})
    assert list(registry.available()) == ["tesseract"]


def test_categorizer_entry_point_and_version_mismatch(monkeypatch):
    ok = FakeCategorizer("fakeai")
    bad = FakeCategorizer("stale")
    bad.api_version = 0
    _patch_eps(monkeypatch, {registry.CATEGORIZER_GROUP: [
        FakeEntryPoint("fakeai", ok), FakeEntryPoint("stale", bad),
    ]})
    assert registry.get_categorizer("fakeai") is ok
    assert registry.get_categorizer("stale") is None


def test_missing_provider_raises_not_installed(monkeypatch):
    _patch_eps(monkeypatch, {})
    with pytest.raises(AIPackagesMissing, match="Provider 'anthropic' is not installed"):
        registry.get_ocr("anthropic")


def test_ocr_anthropic_without_plugin_returns_422(monkeypatch):
    _patch_eps(monkeypatch, {})
    row = SimpleNamespace(ocr_provider="anthropic", max_output_tokens=None, ai_model=None)
    with pytest.raises(HTTPException) as ei:
        _resolve_ocr(row)
    assert ei.value.status_code == 422
    assert ei.value.detail == "Provider 'anthropic' is not installed"


def test_resolve_ocr_builds_via_plugin(monkeypatch):
    _patch_eps(monkeypatch, {registry.OCR_GROUP: [FakeEntryPoint("fakeai", fake_descriptor("fakeai"))]})
    row = SimpleNamespace(ocr_provider="fakeai", max_output_tokens=None, ai_model=None)
    assert _resolve_ocr(row).built_for == "fakeai"


@pytest.mark.asyncio
async def test_categorizer_without_plugin_is_memory_only(monkeypatch):
    _patch_eps(monkeypatch, {})
    row = SimpleNamespace(ocr_provider="anthropic", anthropic_api_key="sk-x", max_output_tokens=None)
    assert _has_ai_credentials(row) is False
    assert await categorizer_service._call_ai(["acme"], [], row) == []
