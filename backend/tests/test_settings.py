import pytest


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
async def test_put_settings_claude_with_key(client):
    res = await client.put("/settings", json={
        "ocr_provider": "claude",
        "anthropic_api_key": "sk-ant-test123",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ocr_provider"] == "claude"
    assert data["anthropic_api_key_set"] is True


@pytest.mark.asyncio
async def test_put_settings_claude_without_key_fails(client):
    res = await client.put("/settings", json={"ocr_provider": "claude"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_key_not_returned_in_get(client):
    await client.put("/settings", json={
        "ocr_provider": "claude",
        "anthropic_api_key": "sk-ant-secret",
    })
    res = await client.get("/settings")
    body = res.text
    assert "sk-ant-secret" not in body
