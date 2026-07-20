"""Tests for the categorizer service — merchant-memory path and provider dispatch."""

import datetime
import decimal
from unittest.mock import MagicMock, patch

import pytest

import tests.conftest as _conf
from src.domain.models.category import Category
from src.domain.models.merchant_memory import MerchantCategoryMemory
from src.domain.models.statement import Statement
from src.domain.models.transaction import Transaction
from src.domain.services.categorizer import _has_ai_credentials, _normalize, categorizer_service


class _MockSettings:
    anthropic_api_key = None
    openai_api_key = None
    gemini_api_key = None
    google_project_id = None
    google_location = None
    ai_api_url = None
    ai_provider = "anthropic"
    ai_model = None
    ai_category_confidence_auto = 0.85
    ai_category_confidence_suggest = 0.6


@pytest.mark.asyncio
async def test_categorizer_merchant_memory_assigns_category():
    """Memory path sets tx.category_id without an API key when confidence >= threshold."""
    async with _conf._TestingSessionLocal() as session:
        cat = Category(name="Food", color="#ff0000", slug="food-cat-test", is_system=False)
        session.add(cat)
        await session.flush()

        session.add(MerchantCategoryMemory(
            description_normalized=_normalize("Coffee Shop"),
            category_id=cat.id,
            source="ai",
            confidence=0.9,
        ))
        await session.flush()

        stmt = Statement(filename="test.pdf")
        session.add(stmt)
        await session.flush()

        tx = Transaction(
            date=datetime.datetime(2026, 5, 15),
            description="Coffee Shop",
            amount=decimal.Decimal("10.00"),
            direction="debit",
            statement_id=stmt.id,
        )
        session.add(tx)
        await session.flush()

        assert tx.category_id is None

        await categorizer_service.categorize_statement(
            stmt.id, [tx], session, _MockSettings()
        )

        assert tx.category_id == cat.id


def test_has_ai_credentials_anthropic():
    s = _MockSettings()
    s.anthropic_api_key = "sk-ant-test"
    s.ai_provider = "anthropic"
    assert _has_ai_credentials(s) is True


def test_no_credentials_skips_ai():
    s = _MockSettings()
    s.ai_provider = "openai"
    s.openai_api_key = None
    assert _has_ai_credentials(s) is False


def test_openai_provider_path():
    """OpenAI provider calls openai.OpenAI without base_url."""
    import json

    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps(
        [{"merchant": "test merchant", "category_id": None, "confidence": 0.5}]
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("src.domain.services.categorizer._openai_lib") as mock_openai:
        mock_openai.OpenAI.return_value = mock_client

        import asyncio

        s = _MockSettings()
        s.ai_provider = "openai"
        s.openai_api_key = "sk-test"

        result = asyncio.get_event_loop().run_until_complete(
            categorizer_service._call_ai(["test merchant"], [], s)
        )

        mock_openai.OpenAI.assert_called_once_with(api_key="sk-test")
        assert result[0]["merchant"] == "test merchant"


def test_local_provider_path():
    """Local provider calls openai.OpenAI with the configured base_url."""
    import json

    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps(
        [{"merchant": "coffee shop", "category_id": 1, "confidence": 0.9}]
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("src.domain.services.categorizer._openai_lib") as mock_openai:
        mock_openai.OpenAI.return_value = mock_client

        import asyncio

        s = _MockSettings()
        s.ai_provider = "local"
        s.ai_api_url = "http://localhost:11434/v1"
        s.ai_model = "llama3"

        result = asyncio.get_event_loop().run_until_complete(
            categorizer_service._call_ai(["coffee shop"], [], s)
        )

        mock_openai.OpenAI.assert_called_once_with(
            api_key="local", base_url="http://localhost:11434/v1"
        )
        assert result[0]["category_id"] == 1


def test_vertex_provider_path():
    """Vertex provider fetches ADC token and calls openai.OpenAI with Vertex base_url."""
    import asyncio
    import json
    import sys

    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps(
        [{"merchant": "cloud store", "category_id": 2, "confidence": 0.8}]
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    mock_creds = MagicMock()
    mock_creds.token = "ya29.test-token"

    # test_storage_gcs.py injects MagicMock() as sys.modules['google'] at collection
    # time, which breaks `import google.auth` if done outside a patched context.
    # Solution: inject all google entries via patch.dict, with `fake_google.auth`
    # pre-bound so that `google.auth.default(...)` in the categorizer reaches the mock.
    mock_google_auth = MagicMock()
    mock_google_auth.default.return_value = (mock_creds, "my-proj")
    fake_google = MagicMock()
    fake_google.auth = mock_google_auth

    fake_modules = {
        'google': fake_google,
        'google.auth': mock_google_auth,
        'google.auth.transport': MagicMock(),
        'google.auth.transport.requests': MagicMock(),
    }
    with patch("src.domain.services.categorizer._openai_lib") as mock_openai, \
         patch.dict(sys.modules, fake_modules):
        mock_openai.OpenAI.return_value = mock_client

        s = _MockSettings()
        s.ai_provider = "vertex"
        s.google_project_id = "my-proj"
        s.google_location = "us-central1"

        result = asyncio.get_event_loop().run_until_complete(
            categorizer_service._call_ai(["cloud store"], [], s)
        )

        call_kwargs = mock_openai.OpenAI.call_args.kwargs
        assert "aiplatform.googleapis.com" in call_kwargs["base_url"]
        assert call_kwargs["api_key"] == "ya29.test-token"
        assert result[0]["category_id"] == 2


def test_account_type_included_in_prompt():
    """account_type is injected into the prompt string when provided."""
    import asyncio
    import json
    captured = {}

    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps([])
    mock_client = MagicMock()

    def capture_create(**kwargs):
        captured['prompt'] = kwargs['messages'][0]['content']
        return mock_resp

    mock_client.chat.completions.create.side_effect = capture_create

    with patch("src.domain.services.categorizer._openai_lib") as mock_openai:
        mock_openai.OpenAI.return_value = mock_client
        s = _MockSettings()
        s.ai_provider = "openai"
        s.openai_api_key = "sk-test"
        asyncio.get_event_loop().run_until_complete(
            categorizer_service._call_ai(["some merchant"], [], s, account_type="credit_card")
        )

    assert "Account type: credit_card" in captured['prompt']


def test_no_account_type_omits_account_line():
    """When account_type is None, no 'Account type' line appears in the prompt."""
    import asyncio
    import json
    captured = {}

    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps([])
    mock_client = MagicMock()

    def capture_create(**kwargs):
        captured['prompt'] = kwargs['messages'][0]['content']
        return mock_resp

    mock_client.chat.completions.create.side_effect = capture_create

    with patch("src.domain.services.categorizer._openai_lib") as mock_openai:
        mock_openai.OpenAI.return_value = mock_client
        s = _MockSettings()
        s.ai_provider = "openai"
        s.openai_api_key = "sk-test"
        asyncio.get_event_loop().run_until_complete(
            categorizer_service._call_ai(["some merchant"], [], s, account_type=None)
        )

    assert "Account type" not in captured['prompt']
