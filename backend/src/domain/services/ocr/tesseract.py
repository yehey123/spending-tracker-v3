import asyncio
import statistics

import numpy as np
import pytesseract
from PIL import Image
from pytesseract import Output

from ..statement_parser import _header_columns
from .base import OCRProvider

_MIN_CONF = 30


def _words(data: dict) -> list[dict]:
    """Keep confident, non-empty words with their box centres."""
    out = []
    for i, text in enumerate(data["text"]):
        text = (text or "").strip().strip("|").strip()  # table grid lines read as "|"
        try:
            conf = float(data["conf"][i])
        except TypeError, ValueError:
            continue
        if not text or conf < _MIN_CONF:
            continue
        x, y, w, h = (data[k][i] for k in ("left", "top", "width", "height"))
        out.append({"text": text, "x": x, "w": w, "h": h, "cx": x + w / 2, "cy": y + h / 2})
    return out


def _skew_slope(words: list[dict], bin_h: float) -> float:
    """Slope (dy/dx) that makes text rows sharpest: maximise row-histogram variance."""
    if len(words) < 4:
        return 0.0
    cx = np.array([w["cx"] for w in words])
    cy = np.array([w["cy"] for w in words])
    best, best_s = 0.0, -1.0
    for deg in np.arange(-6.0, 6.01, 0.25):
        s = np.tan(np.radians(deg))
        y = cy - cx * s
        bins = np.floor((y - y.min()) / bin_h).astype(int)
        score = float(np.sum(np.bincount(bins).astype(float) ** 2))
        if score > best_s + 1e-9:
            best, best_s = s, score
    return best


def _estimate_slope(data: dict) -> float:
    words = _words(data)
    if not words:
        return 0.0
    return _skew_slope(words, max(statistics.median(w["h"] for w in words) / 2, 1.0))


def words_to_lines(data: dict, carry: dict | None = None) -> str:
    """Rebuild reading-order text lines from Tesseract word boxes, correcting skew.

    `carry` (optional, mutable) holds the table header found on an earlier page of the same
    document; it is reused here and filled in when this page finds the first header."""
    words = _words(data)
    if not words:
        return ""
    med_h = statistics.median(w["h"] for w in words)
    slope = _skew_slope(words, max(med_h / 2, 1.0))
    for w in words:
        w["ry"] = w["cy"] - w["cx"] * slope
    words.sort(key=lambda w: w["ry"])
    lines: list[list[dict]] = []
    ys: list[float] = []  # running mean ry per line
    tol = med_h / 2
    for w in words:
        if lines and abs(w["ry"] - ys[-1]) <= tol:
            lines[-1].append(w)
            ys[-1] = sum(v["ry"] for v in lines[-1]) / len(lines[-1])
        else:
            lines.append([w])
            ys.append(w["ry"])
    return "\n".join(
        _render_lines([sorted(line, key=lambda w: w["x"]) for line in lines], med_h, carry)
    )


def _cells(line: list[dict], gap: float) -> list[dict]:
    """Group a line's words (sorted by x) into cells split at horizontal gaps wider than `gap`."""
    cells: list[dict] = []
    for w in line:
        if cells and w["x"] - cells[-1]["x1"] <= gap:
            cells[-1]["text"] += " " + w["text"]
            cells[-1]["x1"] = w["x"] + w["w"]
        else:
            cells.append({"text": w["text"], "x0": w["x"], "x1": w["x"] + w["w"]})
    return cells


def _render_lines(lines: list[list[dict]], med_h: float, carry: dict | None = None) -> list[str]:
    """Join words with spaces; once a table header row is found, emit pipe-delimited rows
    aligned to the header columns (empty cells kept) so Debit/Credit/Balance stay apart."""
    gap = 1.5 * med_h
    out: list[str] = []
    header: list[dict] | None = carry.get("header") if carry is not None else None
    for line in lines:
        cells = _cells(line, gap)
        if header is None and _header_columns([c["text"] for c in cells]):
            header = cells
            if carry is not None:
                carry["header"] = cells
        if header is None:
            out.append(" ".join(w["text"] for w in line))
            continue
        # Zone i spans from the midpoint with the previous header cell
        # to the midpoint with the next.
        edges = [(header[i]["x1"] + header[i + 1]["x0"]) / 2 for i in range(len(header) - 1)]
        bounds = [-1e12, *edges, 1e12]
        row = [""] * len(header)
        for c in cells:
            overlaps = [
                min(c["x1"], bounds[i + 1]) - max(c["x0"], bounds[i]) for i in range(len(header))
            ]
            i = overlaps.index(max(overlaps))
            row[i] = f"{row[i]} {c['text']}".strip()
        out.append(" | ".join(row))
    return out


_CONFIG = "--psm 6 --oem 1"


def _ocr_data(image: Image.Image) -> dict:
    data = pytesseract.image_to_data(image, config=_CONFIG, output_type=Output.DICT)
    angle = float(np.degrees(np.arctan(_estimate_slope(data))))
    if abs(angle) < 0.5:
        return data
    # Tesseract misreads glyphs on tilted text (e.g. "10/" -> "40/"); re-run on a levelled image.
    fill = 255 if image.mode == "L" else (255, 255, 255)
    levelled = image.rotate(angle, resample=Image.BICUBIC, fillcolor=fill)
    return pytesseract.image_to_data(levelled, config=_CONFIG, output_type=Output.DICT)


class TesseractProvider(OCRProvider):
    _carry: dict | None = None

    def start_document(self) -> None:
        """Begin a multi-page document: later pages reuse the first table header found."""
        self._carry = {}

    async def extract_text(self, image: Image.Image) -> str:
        # Run in executor so the blocking Tesseract call doesn't stall the event loop
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            lambda: _ocr_data(image),
        )
        return words_to_lines(data, self._carry)
