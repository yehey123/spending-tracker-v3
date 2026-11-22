"""Tesseract line rebuild from word boxes on a skewed photo-like image."""

import asyncio
import re
from decimal import Decimal

from PIL import Image, ImageDraw, ImageFont

from src.domain.services.ocr.tesseract import TesseractProvider, words_to_lines
from src.domain.services.statement_parser import parse_statement

ROWS = [("10/02/2026", "PAYMENT THANK YOU", "649.89"), ("10/03/2026", "MANGO TREE BGC", "4,610.17")]


def _skewed_statement() -> Image.Image:
    img = Image.new("L", (1800, 600), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=44)
    for i, (date, desc, amt) in enumerate(ROWS):
        y = 200 + i * 70
        draw.text((60, y), date, font=font, fill=0)
        draw.text((520, y), desc, font=font, fill=0)
        draw.text((1500, y), amt, font=font, fill=0)
    # ~9 degrees: the amount column lands about a row above its date.
    return img.rotate(-9, resample=Image.BICUBIC, fillcolor=255)


def _rows_intact(text: str) -> bool:
    lines = text.splitlines()
    return all(
        any(date in ln and amt in ln for ln in lines) for date, _, amt in ROWS
    )


def test_rebuilt_lines_keep_date_and_amount_together():
    text = asyncio.run(TesseractProvider().extract_text(_skewed_statement()))
    assert _rows_intact(text), text


def _fake_data(words: list[tuple[str, int, int, int]]) -> dict:
    """image_to_data dict from (text, left, top, width) tuples; box height 20."""
    return {
        "text": [w[0] for w in words],
        "conf": ["95"] * len(words),
        "left": [w[1] for w in words],
        "top": [w[2] for w in words],
        "width": [w[3] for w in words],
        "height": [20] * len(words),
    }


def test_table_columns_keep_debit_credit_apart():
    words = [
        ("Txn", 10, 10, 30), ("Date", 45, 10, 40), ("Description", 200, 10, 100),
        ("Debit", 500, 10, 50), ("Credit", 600, 10, 50), ("Balance", 700, 10, 60),
        # debit row: amount under Debit, balance under Balance, Credit empty
        ("08-01-2024", 10, 60, 90), ("UPI/DR/728341737715/PAYEL", 200, 60, 100),
        ("Rs.", 490, 60, 25), ("513.47", 520, 60, 60),
        ("Rs.", 700, 60, 25), ("18,916.03", 730, 60, 80),
        # continuation line (no date) must not make a row
        ("14:52:45", 200, 90, 70), ("BHATTACHARYA/", 280, 90, 100),
        # credit row: amount under Credit
        ("09-01-2024", 10, 120, 90), ("NEFT", 200, 120, 40),
        ("Rs.", 580, 120, 25), ("7,675.95", 610, 120, 50),
        ("Rs.", 700, 120, 25), ("24,304.46", 730, 120, 80),
    ]
    text = words_to_lines(_fake_data(words))
    txs = parse_statement(text)
    assert [(t.amount, t.direction) for t in txs] == [
        (Decimal("513.47"), "debit"),
        (Decimal("7675.95"), "credit"),
    ]
