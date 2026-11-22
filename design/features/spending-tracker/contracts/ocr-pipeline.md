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
2. Providers whose descriptor sets `max_side` only: downscale so the longest side is ≤ `max_side` px (LANCZOS). Tesseract sets none, so it receives the original size

---

## Stage 2: OCR Provider Interface

```python
class OCRProvider(ABC):
    async def extract_text(self, image: PIL.Image.Image) -> str:
        ...
```

All providers receive the original image (no preprocessing) and return raw text (no structured parsing at this stage).

**Tesseract is the default and the only provider shipped in core. AI vision providers (Claude, OpenAI, Gemini, Vertex, Ollama) live in the separate plugin repo `yehey123/spending-tracker-ai` and are optional, opt-in alternatives.** The default path needs no API key and no AI service; categorisation falls back to merchant-category memory when no AI plugin is installed or configured.

### Plugin registry
Providers are discovered through `backend/src/plugins/registry.py` using `importlib.metadata` entry-point groups:
- `spending_tracker.ocr_providers`: each entry point resolves to a provider descriptor
- `spending_tracker.categorizers`: each entry point resolves to an AI categoriser

The contract (Protocols and `API_VERSION = 1`) lives in `backend/src/plugins/api.py`. A plugin never imports core. A plugin with a mismatched `api_version`, or one that fails to load, is logged and skipped.

A provider descriptor exposes: `key`, `label`, `api_version`, `config_fields`, `build(settings, ctx)`, `has_credentials(settings)`, `credit_weight`, and optionally `list_models(settings, ctx)` and `max_side`. The registry always includes the built-in `tesseract` descriptor.

### Provider: TesseractProvider (core)
- Default; no API key, no AI
- Lines are rebuilt from word boxes (not from Tesseract's own line output); a skewed page is detected and re-OCR'd
- Table-like rows are emitted as header-aligned pipe-delimited cells

### Optional providers (plugin repo)
Claude, OpenAI (also serves Ollama through its OpenAI-compatible `/v1` endpoint), Gemini and Vertex vision providers, plus their prompts and model-list sync, ship in `spending-tracker-ai`. Prompt building and injection sanitisation stay in core; the categoriser plugin receives the finished prompt. Provider output format is the pipe-delimited line format described in Stage 4.

Provider is resolved at upload time from `app_settings.ocr_provider` (default `tesseract`) through the registry. If the selected provider is not installed, the upload returns 422 `Provider '<key>' is not installed`. If it is installed but `has_credentials` is false, the upload returns 422.

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
app_settings.ocr_provider
    registry.find_ocr(key) is None        → HTTP 422 "Provider '<key>' is not installed"
    "tesseract"                           → TesseractProvider()   (default, core)
    any plugin key (anthropic, openai, gemini, vertex, ollama, ...)
        not descriptor.has_credentials(app_settings) → HTTP 422
        else descriptor.build(app_settings, ctx)     → provider; image resized to descriptor.max_side if set
```

Tesseract needs no key. The 422 is raised before processing.
