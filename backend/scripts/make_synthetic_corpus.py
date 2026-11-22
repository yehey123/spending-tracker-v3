"""Generate a SYNTHETIC OCR test corpus for scripts/ocr_eval.py.

All merchants, banks and amounts are invented. Output is deterministic (seed 42).

For each of 3 layouts (bank_a, bank_b, bank_c) writes:
    <name>_clean.png     white 300 DPI page, rendered text
    <name>_scan.pdf      same page saved as an image-based PDF
    <name>_photo.jpg     degraded copy: rotated, blurred, noisy, uneven light, JPEG q70
    <name>_digital.pdf   text-layer PDF (matplotlib, Type 42 fonts), like an e-statement
and for each of those a <stem>.expected.json in the ocr_eval.py format.

Usage: python -m scripts.make_synthetic_corpus [outdir]
"""

from __future__ import annotations

import json
import random
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable, NamedTuple

import matplotlib
import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SEED = 42
DPI = 300
PAGE = (int(8.5 * DPI), 11 * DPI)  # US Letter at 300 DPI
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ocr_synthetic"
STATEMENT_YEAR = 2026
STATEMENT_MONTH = 10
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
BANK = "SAMPLE BANK"
FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]
MERCHANTS = [
    "JOLLIBEE GREENBELT MAKATI PH",
    "GRAB* TRIP",
    "KAPEHAN NI LOLA MAKATI PH",
    "MANGO TREE BGC TAGUIG PH",
    "PANCIT PALACIO QUEZON CITY PH",
    "SARI-SARI MART ORTIGAS PH",
    "BAYANIHAN BOOKSTORE PASIG PH",
    "LUNCH BOX CEBU IT PARK PH",
    "TUKTUK RIDE CUBAO PH",
    "ISLAND PHARMA MALATE PH",
]
CREDITS = [
    "PAYMENT THANK YOU",
    "CASH REBATE CR",
    "REFUND KAPEHAN NI LOLA MAKATI PH",
]


class Row(NamedTuple):
    date: date
    desc: str
    cents: int
    direction: str  # "debit" | "credit"

    @property
    def amount(self) -> str:
        return f"{self.cents // 100}.{self.cents % 100:02d}"


class Layout(NamedTuple):
    name: str
    title: str
    count: int
    headers: tuple  # (label, x, anchor)
    cells: Callable[[Row, int], list]  # -> strings, one per header column


def _font(size: int):
    for p in FONT_PATHS:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def _money(cents: int) -> str:
    return f"{cents // 100:,}.{cents % 100:02d}"


def _mon_day(d: date) -> str:
    return f"{MONTHS[d.month - 1]} {d.day:02d}"


def _cells_a(r: Row, i: int) -> list:
    # MM/DD/YYYY, description, amount with trailing "-" on credits
    amt = _money(r.cents) + ("-" if r.direction == "credit" else "")
    return [f"{r.date.month:02d}/{r.date.day:02d}/{r.date.year}", r.desc, amt]


def _cells_b(r: Row, i: int) -> list:
    # "Oct 05" posting date, reference, description, amount with " CR" on credits
    amt = _money(r.cents) + (" CR" if r.direction == "credit" else "")
    return [_mon_day(r.date), f"{100000 + i * 37}", r.desc, amt]


def _cells_c(r: Row, i: int) -> list:
    # description first, DD/MM/YYYY date, amount with trailing "-" on credits
    amt = _money(r.cents) + ("-" if r.direction == "credit" else "")
    return [r.desc, f"{r.date.day:02d}/{r.date.month:02d}/{r.date.year}", amt]


LAYOUTS = [
    Layout(
        "bank_a",
        "CREDIT CARD STATEMENT",
        14,
        (("Date", 150, "la"), ("Description", 520, "la"), ("Amount", 2400, "ra")),
        _cells_a,
    ),
    Layout(
        "bank_b",
        "CARD ACTIVITY",
        18,
        (
            ("Posted", 150, "la"),
            ("Reference", 420, "la"),
            ("Description", 900, "la"),
            ("Amount", 2400, "ra"),
        ),
        _cells_b,
    ),
    Layout(
        "bank_c",
        "CARDMEMBER STATEMENT",
        9,
        (("Description", 150, "la"), ("Date", 1700, "la"), ("Amount", 2400, "ra")),
        _cells_c,
    ),
]


def _rows(rng: random.Random, count: int) -> list[Row]:
    credit_idx = set(rng.sample(range(count), rng.randint(1, 2)))
    days = sorted(rng.randint(1, 28) for _ in range(count))
    rows = []
    for i, day in enumerate(days):
        cents = rng.randint(2500, 1_250_000)
        if i in credit_idx:
            rows.append(
                Row(
                    date(STATEMENT_YEAR, STATEMENT_MONTH, day), rng.choice(CREDITS), cents, "credit"
                )
            )
        else:
            rows.append(
                Row(
                    date(STATEMENT_YEAR, STATEMENT_MONTH, day),
                    rng.choice(MERCHANTS),
                    cents,
                    "debit",
                )
            )
    return rows


def _expected(rows: list[Row]) -> dict:
    debits = sum((Decimal(r.amount) for r in rows if r.direction == "debit"), Decimal(0))
    credits = sum((Decimal(r.amount) for r in rows if r.direction == "credit"), Decimal(0))
    return {
        "rows": [
            {"date": r.date.isoformat(), "amount": r.amount, "direction": r.direction} for r in rows
        ],
        "total_debits": f"{debits:.2f}",
        "total_credits": f"{credits:.2f}",
    }


def _items(layout: Layout, rows: list[Row]) -> list[tuple]:
    """Page content as ("text", x, y, text, anchor, size_px) and ("rule", y) in 300-DPI pixels.

    y is measured from the top of the page. Shared by the raster and text-layer renderers.
    """
    exp = _expected(rows)
    items: list[tuple] = [
        ("text", 150, 150, BANK, "la", 64),
        (
            "text",
            150,
            240,
            f"{layout.title} - {MONTHS[STATEMENT_MONTH - 1].upper()} {STATEMENT_YEAR}",
            "la",
            38,
        ),
        ("text", 150, 300, "Account ending 0000 (SAMPLE ONLY)", "la", 34),
    ]
    y = 480
    for label, x, anchor in layout.headers:
        items.append(("text", x, y, label, anchor, 38))
    items.append(("rule", y + 60))
    y += 100
    for i, r in enumerate(rows):
        for text, (_, x, anchor) in zip(layout.cells(r, i), layout.headers):
            items.append(("text", x, y, text, anchor, 38))
        y += 75
    y += 60
    items.append(("rule", y - 30))
    items.append(("text", 150, y, "TOTAL DEBITS", "la", 38))
    items.append(("text", 2400, y, _money(int(Decimal(exp["total_debits"]) * 100)), "ra", 38))
    items.append(("text", 150, y + 75, "TOTAL CREDITS", "la", 38))
    items.append(("text", 2400, y + 75, _money(int(Decimal(exp["total_credits"]) * 100)), "ra", 38))
    return items


def _render(layout: Layout, rows: list[Row]) -> Image.Image:
    img = Image.new("RGB", PAGE, "white")
    d = ImageDraw.Draw(img)
    for item in _items(layout, rows):
        if item[0] == "rule":
            d.line((150, item[1], PAGE[0] - 150, item[1]), fill="black", width=3)
        else:
            _, x, y, text, anchor, size = item
            d.text((x, y), text, font=_font(size), fill="black", anchor=anchor)
    return img


def _write_digital(path: Path, layout: Layout, rows: list[Row]) -> None:
    """Text-layer PDF: real text objects with Type 42 (TrueType) embedded fonts."""
    w, h = PAGE
    with matplotlib.rc_context({"pdf.fonttype": 42, "font.family": "DejaVu Sans"}):
        fig = Figure(figsize=(w / DPI, h / DPI))
        for item in _items(layout, rows):
            if item[0] == "rule":
                fy = 1 - item[1] / h
                fig.add_artist(
                    Line2D(
                        [150 / w, (w - 150) / w],
                        [fy, fy],
                        transform=fig.transFigure,
                        color="black",
                        linewidth=3 * 72 / DPI,
                    )
                )
            else:
                _, x, y, text, anchor, size = item
                fig.text(
                    x / w,
                    1 - y / h,
                    text,
                    ha="left" if anchor == "la" else "right",
                    va="top",
                    fontsize=size * 72 / DPI,
                    color="black",
                )
        fig.savefig(path, format="pdf")


def _degrade(img: Image.Image, rng: random.Random, nrng: np.random.Generator) -> Image.Image:
    angle = rng.uniform(1.5, 3.0) * rng.choice([-1, 1])
    img = img.rotate(angle, resample=Image.BICUBIC, fillcolor="white")
    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
    arr = np.asarray(img).astype(np.float32)
    w = arr.shape[1]
    arr *= np.linspace(0.85, 1.0, w, dtype=np.float32)[None, :, None]
    arr += nrng.normal(0.0, 6.0, arr.shape).astype(np.float32)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _write_json(path: Path, expected: dict) -> None:
    path.write_text(json.dumps(expected, indent=2) + "\n")


def generate(outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    nrng = np.random.default_rng(SEED)
    written: list[Path] = []
    for layout in LAYOUTS:
        rows = _rows(rng, layout.count)
        expected = _expected(rows)
        clean = _render(layout, rows)

        stem = f"{layout.name}_clean"
        clean.save(outdir / f"{stem}.png", "PNG", dpi=(DPI, DPI))
        _write_json(outdir / f"{stem}.expected.json", expected)
        written += [outdir / f"{stem}.png", outdir / f"{stem}.expected.json"]

        stem = f"{layout.name}_scan"
        clean.save(outdir / f"{stem}.pdf", "PDF", resolution=float(DPI))
        _write_json(outdir / f"{stem}.expected.json", expected)
        written += [outdir / f"{stem}.pdf", outdir / f"{stem}.expected.json"]

        stem = f"{layout.name}_photo"
        _degrade(clean, rng, nrng).save(outdir / f"{stem}.jpg", "JPEG", quality=70)
        _write_json(outdir / f"{stem}.expected.json", expected)
        written += [outdir / f"{stem}.jpg", outdir / f"{stem}.expected.json"]

        stem = f"{layout.name}_digital"
        _write_digital(outdir / f"{stem}.pdf", layout, rows)
        _write_json(outdir / f"{stem}.expected.json", expected)
        written += [outdir / f"{stem}.pdf", outdir / f"{stem}.expected.json"]
    return written


def main(argv: list[str]) -> None:
    outdir = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    for p in generate(outdir):
        print(p)


if __name__ == "__main__":
    main(sys.argv)
