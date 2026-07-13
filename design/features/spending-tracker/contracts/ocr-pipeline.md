# OCR Pipeline Contract — Spending Tracker

---

## Overview

```
upload (PNG/JPEG/PDF)
    │
    ├─ PDF? ──────→ pdfplumber → raw text/tables
    │                               │
    │                    image-PDF? └──→ OCR per page (below)
    │
    └─ Image ──→ OpenCV preprocess → OCR provider → raw text
                                                        │
                                         Both paths ───→ StatementParser → ParsedTransaction[]
```

---

## Stage 1: OpenCV Preprocessing (images only)

Input: `PIL.Image.Image` (any mode)
Output: `PIL.Image.Image` (grayscale, thresholded)

Operations (in order):
1. Convert to RGB, then grayscale
2. `fastNlMeansDenoising` (h=10)
3. `adaptiveThreshold` — ADAPTIVE_THRESH_GAUSSIAN_C, THRESH_BINARY, block=11, C=2
4. Deskew: `minAreaRect` on non-zero coords → rotate if `|angle| > 0.5°`

No configuration surface — always runs before any image-based OCR.

---

## Stage 2: OCR Provider Interface

```python
class OCRProvider(ABC):
    async def extract_text(self, image: PIL.Image.Image) -> str:
        ...
```

All providers receive the preprocessed image and return raw text (no structured parsing at this stage).

### Provider: TesseractProvider
- Config: `--psm 6` (uniform block of text)
- No API key
- Default

### Provider: ClaudeVisionProvider
- Constructor: `__init__(self, api_key: str)`
- Model: `claude-sonnet-4-6`
- Prompt instructs Claude to return one transaction per line: `DATE | DESCRIPTION | AMOUNT | DEBIT or CREDIT`
- Dates: MM/DD/YYYY; amounts: numeric only

### Provider: OpenAIVisionProvider
- Constructor: `__init__(self, api_key: str)`
- Model: `gpt-4o`
- Same prompt and output format as ClaudeVisionProvider

Provider is resolved at upload time from `app_settings.ocr_provider`. If the required API key is missing, the upload returns 422.

---

## Stage 3: PDF Extraction (PDFParser)

Input: `bytes` (PDF file content)
Output: `str` (raw text, tables rendered as pipe-delimited rows)

Logic:
1. Open with `pdfplumber`
2. Per page: attempt `page.extract_tables()` first (returns structured rows)
3. If no tables, fall back to `page.extract_text()`
4. Join with newlines
5. If `pdfplumber` returns empty (image-based PDF): per-page rasterize → OpenCV + OCR

---

## Stage 4: StatementParser

Input: `str` (raw OCR or PDF text)
Output: `list[ParsedTransaction]`

```python
@dataclass
class ParsedTransaction:
    date: datetime
    description: str
    amount: Decimal
    direction: str  # "debit" | "credit"
```

### Line classification priority
1. **Pipe-delimited** (`DATE | DESCRIPTION | AMOUNT | DIRECTION`): used when AI providers return structured output
2. **Regex pattern**: matches common statement line formats
   - Date patterns: `MM/DD/YYYY`, `MM/DD/YY`, `DD/MM/YYYY`, `DD-MM-YYYY`, `MMM DD`
   - Amount: `\d{1,3}(?:,\d{3})*(?:\.\d{2})?`
   - Direction hint: trailing `CR`, `DR`, `CREDIT`, `DEBIT`; default = `debit` if absent
3. Lines that match neither pattern are skipped (header rows, blank lines, totals)

### Known heuristic (document here, not in code)
- Amount followed by `CR` or `CREDIT` → direction = credit
- Lines where amount matches the statement running balance (very large round number) → skip
- Duplicate detection is NOT done at parse time; it's a future story

---

## Provider Selection Logic (backend)

```
GET /settings → ocr_provider value
    "tesseract" → TesseractProvider()
    "claude"    → ClaudeVisionProvider(api_key=app_settings.anthropic_api_key)
    "openai"    → OpenAIVisionProvider(api_key=app_settings.openai_api_key)
```

If selected provider's API key is null → raise HTTP 422 before processing.
