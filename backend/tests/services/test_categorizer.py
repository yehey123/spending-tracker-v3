"""Tests for the categorizer service — merchant-memory path (no API key required)."""

import datetime
import decimal

import pytest

import tests.conftest as _conf
from src.domain.models.category import Category
from src.domain.models.merchant_memory import MerchantCategoryMemory
from src.domain.models.statement import Statement
from src.domain.models.transaction import Transaction
from src.domain.services.categorizer import _normalize, categorizer_service


class _MockSettings:
    anthropic_api_key = None
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
