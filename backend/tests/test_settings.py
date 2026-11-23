from types import SimpleNamespace

import pytest

from src.plugins import registry
from tests.plugin_fakes import FakeEntryPoint, fake_descriptor


def _install_fake_ai(monkeypatch, key="anthropic"):
    desc = fake_descriptor(key=key)
    desc.config_fields = (
        SimpleNamespace(name="anthropic_api_key", label="API key", secret=True, required=True),
    )
    desc.has_credentials = lambda s: bool(getattr(s, "anthropic_api_key", None))
    registry.reset_cache()
    monkeypatch.setattr(
        registry.importlib.metadata,
        "entry_points",
        lambda group: [FakeEntryPoint(key, desc)] if group == registry.OCR_GROUP else [],
    )
    return desc


@pytest.mark.asyncio
async def test_get_settings_default(client):
    res = await client.get("/settings")
    assert res.status_code == 200
    data = res.json()
    assert data["ocr_provider"] == "tesseract"
    assert data["anthropic_api_key_set"] is False
    assert data["openai_api_key_set"] is False


@pytest.mark.asyncio
async def test_put_settings_tesseract(client):
    res = await client.put("/settings", json={"ocr_provider": "tesseract"})
    assert res.status_code == 200
    assert res.json()["ocr_provider"] == "tesseract"


@pytest.mark.asyncio
async def test_default_available_providers_is_tesseract_only(client):
    registry.reset_cache()
    data = (await client.get("/settings")).json()
    assert data["available_providers"] == [
        {"key": "tesseract", "label": "Tesseract (local)", "config_fields": []}
    ]
    assert data["provider_installed"] is True


@pytest.mark.asyncio
async def test_put_unknown_provider_without_plugin_422(client):
    registry.reset_cache()
    res = await client.put("/settings", json={"ocr_provider": "anthropic"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_put_provider_with_plugin_accepted_and_listed(client, monkeypatch):
    _install_fake_ai(monkeypatch)
    res = await client.put("/settings", json={
        "ocr_provider": "anthropic",
        "anthropic_api_key": "sk-ant-test123",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ocr_provider"] == "anthropic"
    assert data["anthropic_api_key_set"] is True
    assert data["provider_installed"] is True
    keys = [p["key"] for p in data["available_providers"]]
    assert keys == ["tesseract", "anthropic"]
    field = data["available_providers"][1]["config_fields"][0]
    assert field["name"] == "anthropic_api_key" and field["secret"] is True and field["set"] is True


@pytest.mark.asyncio
async def test_put_provider_without_key_fails(client, monkeypatch):
    _install_fake_ai(monkeypatch)
    res = await client.put("/settings", json={"ocr_provider": "anthropic"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_provider_installed_false_when_plugin_removed(client, monkeypatch):
    _install_fake_ai(monkeypatch)
    await client.put("/settings", json={
        "ocr_provider": "anthropic", "anthropic_api_key": "sk-ant-x",
    })
    registry.reset_cache()
    monkeypatch.undo()
    data = (await client.get("/settings")).json()
    assert data["ocr_provider"] == "anthropic"
    assert data["provider_installed"] is False


@pytest.mark.asyncio
async def test_models_empty_without_plugins(client):
    res = await client.get("/settings/models")
    assert res.status_code == 200
    assert res.json()["models"] == []


@pytest.mark.asyncio
async def test_key_not_returned_in_get(client, monkeypatch):
    _install_fake_ai(monkeypatch)
    await client.put("/settings", json={
        "ocr_provider": "anthropic",
        "anthropic_api_key": "sk-ant-secret",
    })
    res = await client.get("/settings")
    assert "sk-ant-secret" not in res.text
