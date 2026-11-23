# OCR Pipeline Contract — Spending Tracker

---

## Overview

```
upload (PNG/JPEG/PDF)
    │
    ├─ PDF? ──────→ pdfplumber → raw text/tables
    │                               │
    │                    image-PDF? └──→ render at native DPI (≤300) → OCR per page (below)
    │
    └─ Image ──→ OCR provider (no preprocess) → raw text
                                                        │
                                         Both paths ───→ StatementParser → ParsedTransaction[]
```

---

## Stage 1: Image Preparation (images only)

Input: `PIL.Image.Image` (any mode)
Output: `PIL.Image.Image` (original pixels, metadata stripped)

No OpenCV step runs on any path. Tesseract's own binarisation scores better on the original image, and AI vision models want colour. `preprocessor.py` remains in the tree but the pipeline does not call it.

Operations (in order):
1. Re-encode from raw pixel bytes (L or RGB) to strip EXIF, ICC and text chunks
2. AI vision providers only: downscale so the longest side is ≤ 1536 px (LANCZOS)

---

## Stage 2: OCR Provider Interface

```python
class OCRProvider(ABC):
    async def extract_text(self, image: PIL.Image.Image) -> str:
        ...
```

All providers receive the original image (no preprocessing) and return raw text (no structured parsing at this stage).

**Tesseract is the default. AI vision providers (Claude, OpenAI, Gemini, Vertex, Ollama) are optional, opt-in alternatives.** The default path needs no API key and no AI service; categorisation falls back to merchant-category memory when no AI is configured.

### Provider: TesseractProvider
- Default; no API key, no AI
- Lines are rebuilt from word boxes (not from Tesseract's own line output); a skewed page is detected and re-OCR'd
- Table-like rows are emitted as header-aligned pipe-delimited cells

### Provider: ClaudeVisionProvider
- Constructor: `__init__(self, api_key: str)`
- Model: `claude-sonnet-4-6`
- Prompt instructs Claude to return one transaction per line: `DATE | DESCRIPTION | AMOUNT | DEBIT or CREDIT`
- Dates: MM/DD/YYYY; amounts: numeric only

### Provider: OpenAIVisionProvider
- Constructor: `__init__(self, api_key: str)`
- Model: `gpt-4o`
- Same prompt and output format as ClaudeVisionProvider
- Also serves Ollama (OpenAI-compatible `/v1` endpoint)

### Other optional providers
- `GeminiVisionProvider`, `VertexVisionProvider`: same role as the other AI vision providers; opt-in only.

Provider is resolved at upload time from `app_settings.ocr_provider` (default `tesseract`). If an AI provider is selected and its required API key is missing, the upload returns 422.

---

## Stage 3: PDF Extraction (PDFParser)

Input: `bytes` (PDF file content)
Output: `str` (raw text, tables rendered as pipe-delimited rows)

Logic:
1. Open with `pdfplumber`
2. Per page: attempt `page.extract_tables()` first (returns structured rows)
3. If no tables, fall back to `page.extract_text()`
4. Join with newlines
5. If `pdfplumber` returns empty (image-based PDF): per-page render at the scan's native DPI (capped at 300) → OCR (no OpenCV)
6. Tesseract only: the table header row is carried across pages so continuation pages keep their column alignment

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
1. **Pipe-delimited** (`DATE | DESCRIPTION | AMOUNT | DIRECTION`): AI provider output, and header-aligned cells from Tesseract and PDF tables (Debit/Credit columns, or Amount + Balance)
2. **Regex pattern**: matches common statement line formats
   - Date patterns: `MM/DD/YYYY`, `MM/DD/YY`, `DD/MM/YYYY`, `DD-MM-YYYY`, `MMM DD`; the date may appear anywhere in the line; DD/MM vs MM/DD is inferred from the statement's dates
   - Amount: `\d{1,3}(?:,\d{3})*(?:\.\d{2})?`
   - Direction hint: `CR`/`Cr`, `DR`/`Dr`, `CREDIT`, `DEBIT`, or separate Debit/Credit columns; default = `debit` if absent
   - Wrapped rows (description continued on the next line) are joined to their transaction
3. Lines that match neither pattern are skipped (header rows, blank lines, totals)

### Known heuristic (document here, not in code)
- Amount followed by `CR` or `CREDIT` → direction = credit
- Lines where amount matches the statement running balance (very large round number) → skip
- Duplicate detection is NOT done at parse time; it's a future story
- `receipt_parser.py` (`detect_kind` / `parse_receipt`) exists for single-receipt images but is NOT wired into the pipeline; all uploads go through StatementParser

---

## Provider Selection Logic (backend)

```
GET /settings → ocr_provider value
    "tesseract" → TesseractProvider()          (default)
    "anthropic" → ClaudeVisionProvider(api_key=app_settings.anthropic_api_key)   (optional)
    "openai"    → OpenAIVisionProvider(api_key=app_settings.openai_api_key)      (optional)
    "gemini" / "vertex" / "ollama" → optional AI vision providers
```

If an AI provider is selected and its API key is null → raise HTTP 422 before processing. Tesseract needs no key.
