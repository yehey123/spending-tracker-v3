import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class ParsedReceipt:
    date: datetime | None
    total: Decimal | None
    merchant: str | None


_NUM_RE = re.compile(r"\d[\d.,]*\d|\d")
_THOUSANDS_RE = re.compile(r"\d{1,3}(?:[.,]\d{3})+")
_DECIMAL_RE = re.compile(r"(\d[\d.,]*)[.,](\d{1,2})")

_TOTAL_RE = re.compile(r"\b(GRAND\s*TOTAL|AMOUNT\s*DUE|TOTAL|JUMLAH|NETT?)\b", re.IGNORECASE)
_STRONG_TOTAL_RE = re.compile(
    r"GRAND\s*TOTAL|AMOUNT\s*DUE|TOTAL\s*(RM|RP|\(?\s*(INCL|ROUND))|TOTAL\s*:?\s*(RM|RP|\$)",
    re.IGNORECASE,
)
_TOTAL_EXCLUDE_RE = re.compile(
    r"SUB\s*-?\s*TOTAL|QTY|QUANTITY|DISC|SAVING|CASH|CHANGE|TUNAI|TENDER|EXCL|ITEMS?\b|TAX\s*TOTAL",
    re.IGNORECASE,
)

_DMY_RE = re.compile(r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4}|\d{2})(?!\d)")
_YMD_RE = re.compile(r"(?<!\d)(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})(?!\d)")
_NAMED_RE = re.compile(r"(?<!\d)(\d{1,2})[ \-]*([A-Za-z]{3,9})[ \-,.]*(\d{4}|\d{2})(?!\d)")
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

_DATED_LINE_RE = re.compile(
    r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\b[A-Za-z]{3} \d{1,2}\b).*\d[\d,]*\.\d{2}"
)
_STATEMENT_STRONG = re.compile(
    r"\bSTATEMENT\b|TOTAL\s+DEBITS|TOTAL\s+CREDITS|\bBALANCE\b|CREDIT\s+LIMIT|\bTRANSACTIONS?\b",
    re.IGNORECASE,
)
_CARD_RE = re.compile(r"\bCARD\b", re.IGNORECASE)
_RECEIPT_KEYWORDS = [
    re.compile(p, re.IGNORECASE)
    for p in (r"\bTOTAL\b", r"SUB\s*TOTAL", r"\bVAT\b", r"\bGST\b", r"\bSST\b", r"\bTAX\b",
              r"\bCHANGE\b", r"\bCASH\b", r"\bTUNAI\b", r"\bQTY\b", r"\bRECEIPT\b", r"\bINVOICE\b")
]


def _normalize_amount(tok: str) -> Decimal | None:
    if tok.isdigit():
        return Decimal(tok)
    if _THOUSANDS_RE.fullmatch(tok):  # 57.000 / 57,000 / 1.591.600: IDR style, no decimals
        return Decimal(re.sub(r"[.,]", "", tok))
    m = _DECIMAL_RE.fullmatch(tok)
    if m:
        return Decimal(f"{re.sub(r'[.,]', '', m.group(1))}.{m.group(2)}")
    return None


def _amounts(line: str) -> list[Decimal]:
    out = []
    for m in _NUM_RE.finditer(line):
        v = _normalize_amount(m.group())
        if v is not None:
            out.append(v)
    return out


def _parse_total(lines: list[str]) -> Decimal | None:
    strong: Decimal | None = None
    plain: Decimal | None = None
    for i, line in enumerate(lines):
        if not _TOTAL_RE.search(line) or _TOTAL_EXCLUDE_RE.search(line):
            continue
        amts = _amounts(line)
        if not amts and i + 1 < len(lines):
            amts = _amounts(lines[i + 1])
        if not amts:
            continue
        if _STRONG_TOTAL_RE.search(line):
            if strong is None:
                strong = amts[-1]
        elif plain is None:
            plain = amts[-1]
    if strong is not None:
        return strong
    if plain is not None:
        return plain
    every = [a for line in lines for a in _amounts(line)]
    return max(every) if every else None


def _year(y: str) -> int:
    return int(y) + 2000 if len(y) == 2 else int(y)


def _parse_date(text: str) -> datetime | None:
    for m in _YMD_RE.finditer(text):
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
    for m in _DMY_RE.finditer(text):
        a, b, y = int(m.group(1)), int(m.group(2)), _year(m.group(3))
        # DD/MM preferred (MYR/IDR); fall back to MM/DD only when DD/MM is impossible
        for day, month in ((a, b), (b, a)):
            try:
                return datetime(y, month, day)
            except ValueError:
                continue
    for m in _NAMED_RE.finditer(text):
        mon = m.group(2)[:3].lower()
        if mon in _MONTHS:
            try:
                return datetime(_year(m.group(3)), _MONTHS.index(mon) + 1, int(m.group(1)))
            except ValueError:
                continue
    return None


def _parse_merchant(lines: list[str]) -> str | None:
    for line in lines[:8]:
        if sum(c.isalpha() for c in line) >= 3 and not _TOTAL_RE.search(line):
            return line
    return None


def parse_receipt(text: str) -> ParsedReceipt:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return ParsedReceipt(
        date=_parse_date(text),
        total=_parse_total(lines),
        merchant=_parse_merchant(lines),
    )


def detect_kind(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    dated = sum(1 for ln in lines if _DATED_LINE_RE.search(ln))
    stmt = (3 if dated >= 3 else 0) + 2 * len(_STATEMENT_STRONG.findall(text))
    stmt += 1 if _CARD_RE.search(text) else 0
    rcpt = sum(1 for p in _RECEIPT_KEYWORDS if p.search(text))
    return "statement" if stmt > rcpt else "receipt"
