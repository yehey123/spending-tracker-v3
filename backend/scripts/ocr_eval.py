"""Score OCR providers against a private corpus of real statements.

Corpus (git- and docker-ignored): tests/fixtures/private/ocr/
    <name>.pdf | .png | .jpg      the statement
    <name>.expected.json          {"rows": [{"date": "2026-01-05", "amount": "123.45",
                                             "direction": "debit"}, ...],
                                   "total_debits": "456.78", "total_credits": "100.00"}

Run in the dev image, corpus mounted read-only (it is never copied into the image):
    docker compose run --rm -v ./backend/tests/fixtures/private/ocr:/corpus:ro \
        -e GOOGLE_PROJECT_ID=<id> backend \
        python -m scripts.ocr_eval /corpus tesseract vertex:google/gemini-2.5-flash \
        vertex:<flash-lite model id>

Prints per-sample scores and totals only — never statement text.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import re
import sys
import time
from decimal import Decimal
from pathlib import Path

from PIL import Image

from src.domain.services.pdf_parser import extract_pdf_text
from src.domain.services.receipt_parser import detect_kind, parse_receipt
from src.domain.services.statement_parser import parse_statement
from src.plugins import registry

_TOKENS_RE = re.compile(r"output_tokens=(\d+)")


class _TokenCounter(logging.Handler):
    """Sums output_tokens from VertexVisionProvider's existing log line."""

    def __init__(self) -> None:
        super().__init__()
        self.total = 0

    def emit(self, record: logging.LogRecord) -> None:
        m = _TOKENS_RE.search(record.getMessage())
        if m:
            self.total += int(m.group(1))


def _provider(spec: str):
    """Resolve `name[:model]` through the plugin registry; returns (provider, max_side)."""
    from types import SimpleNamespace

    name, _, model = spec.partition(":")
    try:
        desc = registry.get_ocr(name)
    except Exception as e:
        raise SystemExit(f"Unknown provider: {spec} ({e})")
    settings = SimpleNamespace(
        ocr_provider=name,
        ai_model=model or None,
        max_output_tokens=None,
        google_project_id=os.environ.get("GOOGLE_PROJECT_ID"),
        google_location=os.environ.get("GOOGLE_LOCATION", "us-central1"),
    )
    return desc.build(settings, registry.make_context(settings))


async def _ocr(path: Path, provider, is_tesseract: bool, max_side: int | None = None) -> str:
    content = path.read_bytes()
    if path.suffix.lower() == ".pdf":
        return await extract_pdf_text(content, provider)
    img = Image.open(io.BytesIO(content)).convert("RGB")
    if not is_tesseract and max_side and max(img.size) > max_side:
        s = max_side / max(img.size)
        img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    return await provider.extract_text(img)


def _key(date: str | object, amount, direction: str) -> tuple:
    # Month/day only: "%b %d" statement dates get the current year from the parser.
    d = date if not isinstance(date, str) else None
    month_day = (d.month, d.day) if d else tuple(int(x) for x in date.split("-")[1:3])
    return (month_day, Decimal(str(amount)), direction)


def score(expected: dict, parsed: list) -> dict:
    want = [_key(r["date"], r["amount"], r["direction"]) for r in expected["rows"]]
    got = [_key(t.date, t.amount, t.direction) for t in parsed]
    remaining = list(got)
    hits = 0
    for k in want:
        if k in remaining:
            remaining.remove(k)
            hits += 1
    want_amounts = sorted(k[1] for k in want)
    got_amounts = sorted(k[1] for k in got)
    amount_hits = sum(1 for a in want_amounts if a in got_amounts and not got_amounts.remove(a))
    debits = sum((t.amount for t in parsed if t.direction == "debit"), Decimal(0))
    credits = sum((t.amount for t in parsed if t.direction == "credit"), Decimal(0))
    return {
        "row_recall": hits / len(want) if want else 1.0,
        "row_precision": hits / len(got) if got else 0.0,
        "amount_match": amount_hits / len(want) if want else 1.0,
        "reconciles": debits == Decimal(expected["total_debits"])
        and credits == Decimal(expected["total_credits"]),
    }


def score_receipt(expected: dict, text: str) -> dict:
    parsed = parse_receipt(text)
    want_total = Decimal(expected["total"]) if expected.get("total") is not None else None
    date_ok = None
    if expected.get("date"):
        date_ok = parsed.date is not None and parsed.date.date().isoformat() == expected["date"]
    return {
        "kind_ok": detect_kind(text) == "receipt",
        "total_ok": parsed.total == want_total,
        "date_ok": date_ok,
    }


async def main(corpus: Path, specs: list[str], limit: int | None = None) -> None:
    samples = sorted(
        p for p in corpus.iterdir() if p.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"}
    )
    if not samples:
        raise SystemExit(f"No samples in {corpus}")
    counter = _TokenCounter()
    logging.getLogger("spending_tracker_ai.vertex").addHandler(counter)
    logging.getLogger("spending_tracker_ai.vertex").setLevel(logging.INFO)

    if limit:
        samples = samples[:limit]

    rows = []
    receipt_rows = []
    for spec in specs:
        provider = _provider(spec)
        _d = registry.find_ocr(spec.partition(":")[0])
        max_side = getattr(_d, "max_side", None)
        for path in samples:
            expected = json.loads(path.with_suffix(".expected.json").read_text())
            if expected.get("kind") == "receipt":
                t0 = time.monotonic()
                try:
                    r = score_receipt(
                        expected, await _ocr(path, provider, spec == "tesseract", max_side)
                    )
                except Exception as e:  # report and keep going
                    r = {
                        "kind_ok": False,
                        "total_ok": False,
                        "date_ok": None,
                        "error": type(e).__name__,
                    }
                r.update(provider=spec, sample=path.name)
                receipt_rows.append(r)
                date_s = "-" if r["date_ok"] is None else ("Y" if r["date_ok"] else "N")
                print(
                    f"{spec:40} {path.name:30} kind={'Y' if r['kind_ok'] else 'N'} "
                    f"total={'Y' if r['total_ok'] else 'N'} date={date_s} "
                    f"{round(time.monotonic() - t0, 1)}s {r.get('error', '')}"
                )
                continue
            before, t0 = counter.total, time.monotonic()
            try:
                parsed = parse_statement(await _ocr(path, provider, spec == "tesseract", max_side))
                s = score(expected, parsed)
            except Exception as e:  # report and keep going
                s = {
                    "row_recall": 0.0,
                    "row_precision": 0.0,
                    "amount_match": 0.0,
                    "reconciles": False,
                    "error": type(e).__name__,
                }
            s.update(
                provider=spec,
                sample=path.name,
                seconds=round(time.monotonic() - t0, 1),
                output_tokens=counter.total - before,
            )
            rows.append(s)
            print(
                f"{spec:40} {path.name:30} recall={s['row_recall']:.3f} "
                f"prec={s['row_precision']:.3f} amt={s['amount_match']:.3f} "
                f"rec={'Y' if s['reconciles'] else 'N'} {s['seconds']}s "
                f"tok={s['output_tokens']} {s.get('error', '')}"
            )

    if receipt_rows:
        print("\nRECEIPT SUMMARY")
        for spec in specs:
            r = [x for x in receipt_rows if x["provider"] == spec]
            dated = [x for x in r if x["date_ok"] is not None]
            print(
                f"{spec:40} n={len(r)} "
                f"kind_acc={sum(x['kind_ok'] for x in r) / len(r):.3f} "
                f"total_acc={sum(x['total_ok'] for x in r) / len(r):.3f} "
                f"date_acc={sum(x['date_ok'] for x in dated) / len(dated) if dated else 0:.3f} "
                f"(date n={len(dated)})"
            )

    if not rows:
        return
    print("\nSUMMARY (pass bar: amount ≥0.99, recall ≥0.98, reconciles ≥0.95)")
    for spec in specs:
        r = [x for x in rows if x["provider"] == spec]
        n = len(r)
        print(
            f"{spec:40} recall={sum(x['row_recall'] for x in r) / n:.3f} "
            f"amt={sum(x['amount_match'] for x in r) / n:.3f} "
            f"reconciles={sum(x['reconciles'] for x in r) / n:.3f} "
            f"tokens={sum(x['output_tokens'] for x in r)}"
        )

    out = Path(os.environ.get("OCR_EVAL_CSV", "/tmp/ocr_eval.csv"))
    with out.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "provider",
                "sample",
                "row_recall",
                "row_precision",
                "amount_match",
                "reconciles",
                "seconds",
                "output_tokens",
                "error",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"CSV: {out}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    limit = None
    if "--limit" in argv:
        i = argv.index("--limit")
        limit = int(argv[i + 1])
        del argv[i : i + 2]
    if len(argv) < 2:
        raise SystemExit(__doc__)
    asyncio.run(main(Path(argv[0]), argv[1:], limit))
