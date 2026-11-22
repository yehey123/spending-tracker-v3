"""Tesseract line rebuild from word boxes on a skewed photo-like image."""

import asyncio
import re

import pytesseract
from PIL import Image, ImageDraw, ImageFont

from src.domain.services.ocr.tesseract import TesseractProvider

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


def test_old_image_to_string_path_splits_rows():
    old = pytesseract.image_to_string(_skewed_statement(), config="--psm 6 --oem 1")
    print(old)
    assert not _rows_intact(old), "image_to_string kept rows together; test no longer discriminates"
