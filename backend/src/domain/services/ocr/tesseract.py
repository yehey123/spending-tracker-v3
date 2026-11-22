import asyncio
import statistics

import numpy as np
import pytesseract
from PIL import Image
from pytesseract import Output

from .base import OCRProvider

_MIN_CONF = 30


def _words(data: dict) -> list[dict]:
    """Keep confident, non-empty words with their box centres."""
    out = []
    for i, text in enumerate(data["text"]):
        text = (text or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
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


def words_to_lines(data: dict) -> str:
    """Rebuild reading-order text lines from Tesseract word boxes, correcting skew."""
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
        " ".join(w["text"] for w in sorted(line, key=lambda w: w["x"])) for line in lines
    )


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
    async def extract_text(self, image: Image.Image) -> str:
        # Run in executor so the blocking Tesseract call doesn't stall the event loop
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            lambda: _ocr_data(image),
        )
        return words_to_lines(data)
