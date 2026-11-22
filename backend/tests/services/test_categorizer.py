"""Tests for the categorizer service — merchant-memory path and provider dispatch."""

import datetime
import decimal

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
    ocr_provider = "anthropic"
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


def test_no_credentials_skips_ai():
    s = _MockSettings()
    s.ai_provider = "openai"
    s.openai_api_key = None
    assert _has_ai_credentials(s) is False


def test_account_type_included_in_prompt(monkeypatch):
    """account_type is injected into the prompt string when provided."""
    import asyncio

    from tests.plugin_fakes import install_fake_categorizer
    fake = install_fake_categorizer(monkeypatch, "openai")
    s = _MockSettings()
    s.ocr_provider = "openai"
    asyncio.get_event_loop().run_until_complete(
        categorizer_service._call_ai(["some merchant"], [], s, account_type="credit_card")
    )
    assert "Account type: credit_card" in fake.prompts[0]


def test_no_account_type_omits_account_line(monkeypatch):
    """When account_type is None, no 'Account type' line appears in the prompt."""
    import asyncio

    from tests.plugin_fakes import install_fake_categorizer
    fake = install_fake_categorizer(monkeypatch, "openai")
    s = _MockSettings()
    s.ocr_provider = "openai"
    asyncio.get_event_loop().run_until_complete(
        categorizer_service._call_ai(["some merchant"], [], s, account_type=None)
    )
    assert "Account type" not in fake.prompts[0]
