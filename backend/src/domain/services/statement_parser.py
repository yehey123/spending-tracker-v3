import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class ParsedTransaction:
    date: datetime
    description: str
    amount: Decimal
    direction: str  # "debit" | "credit"
    category_name: str | None = None  # populated when OCR provider bundles categorization


_DATE_FORMATS = [
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%b %d",
]

_PIPE_RE = re.compile(
    r"^\s*(?P<date>[^|]+?)\s*\|\s*(?P<desc>[^|]+?)\s*\|\s*(?P<amount>[^|]+?)\s*\|\s*(?P<dir>[^|]+?)(\s*\|\s*(?P<cat>[^|]*?))?\s*$",
    re.IGNORECASE,
)
# Matches amounts like 1,234.56 or 1234.56, optionally followed by - (credit indicator)
_AMOUNT_RE = re.compile(r"(?<![\d.,])((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?)\s*(-)?")
_DIR_RE = re.compile(r"\b(CR|CREDIT|DR|DEBIT)\b", re.IGNORECASE)
# Trailing city/country noise common in Philippine bank statements: "MAKATI PH", "PASIG CITY PH"
_LOCATION_NOISE_RE = re.compile(r"\s+[A-Z][A-Z\s]*\bPH\s*$")
_SKIP_AMOUNT = Decimal("999999")
_SLASH_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/\d{2,4}\b")
# Numeric date anywhere in a line (layouts where the description precedes the date)
_DATE_ANYWHERE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
_DAY_FIRST_FORMATS = ["%d/%m/%Y", "%d/%m/%y"]


def _is_day_first(text: str) -> bool:
    """True when any slash-date in the statement has a first field > 12 (so it is DD/MM)."""
    return any(int(m.group(1)) > 12 for m in _SLASH_DATE_RE.finditer(text))


def _parse_date(s: str, day_first: bool = False) -> datetime | None:
    s = s.strip()
    current_year = datetime.now().year
    formats = _DAY_FIRST_FORMATS + _DATE_FORMATS if day_first else _DATE_FORMATS
    for fmt in formats:
        try:
            if "%Y" not in fmt and "%y" not in fmt:
                dt = datetime.strptime(f"{s} {current_year}", f"{fmt} %Y")
            else:
                dt = datetime.strptime(s, fmt)
            return dt
        except ValueError:
            continue
    return None


def _parse_amount(s: str) -> Decimal | None:
    s = s.strip().replace(",", "")
    try:
        return Decimal(s)
    except Exception:
        return None


def _direction_from_token(token: str) -> str:
    t = token.strip().upper()
    if t in ("CR", "CREDIT"):
        return "credit"
    return "debit"


def _header_columns(cells: list[str]) -> dict[str, int] | None:
    """Map column roles from a table header row; None when the row is not a usable header."""
    if any(ch.isdigit() for c in cells for ch in c):
        return None
    cols: dict[str, int] = {}
    for i, c in enumerate(cells):
        c = c.lower()
        if "date" in c:
            cols.setdefault("date", i)
        elif any(k in c for k in ("description", "narration", "particulars")):
            cols.setdefault("desc", i)
        elif "debit" in c or "withdrawal" in c:
            cols.setdefault("debit", i)
        elif "credit" in c or "deposit" in c:
            cols.setdefault("credit", i)
        elif "cr/dr" in c or "dr/cr" in c:
            cols.setdefault("crdr", i)
        elif "amount" in c:
            cols.setdefault("amount", i)
    has_direction = "debit" in cols or "credit" in cols or ("crdr" in cols and "amount" in cols)
    if "date" in cols and "amount" in cols and not has_direction:
        # OCR often drops the Cr/Dr heading: accept Amount + Balance; direction comes from row tokens.
        for i, c in enumerate(cells):
            if "balance" in c.lower():
                cols.setdefault("balance", i)
        return cols if "balance" in cols else None
    return cols if "date" in cols and has_direction else None


_BLOCK_AMT_RE = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?!\d)")
_BLOCK_DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b")
# CR/DR token set apart from words and from "/" (so "UPI/CR/123" in a description is not a token)
_BLOCK_DIR_RE = re.compile(r"(?<![A-Za-z/])(cr|dr)\.?(?![A-Za-z/])", re.IGNORECASE)
_BLOCK_SKIP_RE = re.compile(r"\b(opening|closing|brought forward|carried forward)\b", re.IGNORECASE)


def _is_amount_header(line: str) -> bool:
    """Digit-free header line naming Amount and Balance columns (Cr/Dr heading may be missing)."""
    low = line.lower()
    return (
        not any(ch.isdigit() for ch in line)
        and re.search(r"\bamount\b", low) is not None
        and re.search(r"\bbalance\b", low) is not None
    )


def _parse_blocks(text: str, day_first: bool) -> list[ParsedTransaction]:
    """Wrapped-row layout: a line with a date starts a transaction; dateless lines attach to it;
    the first line carrying amounts supplies amount (and balance); direction from a CR/DR token,
    else from the balance change."""
    results: list[ParsedTransaction] = []
    cur: dict | None = None
    prev_balance: Decimal | None = None

    def flush() -> None:
        nonlocal cur, prev_balance
        if cur and cur["amounts"]:
            amount = cur["amounts"][0]
            balance = cur["amounts"][1] if len(cur["amounts"]) > 1 else None
            if (
                balance is None
                and prev_balance
                and amount != prev_balance
                and Decimal("0.5") <= amount / prev_balance <= 2
            ):
                # OCR lost the amount cell; the lone figure is a running balance close to the last one.
                balance, amount = amount, abs(amount - prev_balance)
            if cur["dir"]:
                direction = cur["dir"]
            elif balance is not None and prev_balance is not None:
                direction = "credit" if balance > prev_balance else "debit"
            else:
                direction = "debit"
            if balance is not None:
                prev_balance = balance
            results.append(ParsedTransaction(
                date=cur["date"], description=" ".join(cur["desc"]).strip(),
                amount=amount, direction=direction))
        cur = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _is_amount_header(line):
            flush()
            continue
        if _BLOCK_SKIP_RE.search(line):
            flush()
            continue
        dm = _BLOCK_DATE_RE.search(line)
        date = _parse_date(dm.group(), day_first) if dm else None
        if date is not None:
            flush()
            cur = {"date": date, "amounts": [], "dir": None, "desc": []}
        if cur is None:
            continue
        if not cur["amounts"]:
            amts = [_parse_amount(a) for a in _BLOCK_AMT_RE.findall(line)]
            amts = [a for a in amts if a is not None and a <= _SKIP_AMOUNT]
            if amts:
                cur["amounts"] = amts[:2]
                tok = _BLOCK_DIR_RE.search(line)
                if tok:
                    cur["dir"] = _direction_from_token(tok.group(1))
                continue
        desc = _BLOCK_DATE_RE.sub("", line).replace("|", " ").strip()
        if desc:
            cur["desc"].append(desc)
    flush()
    return results


def _cell_amount(cell: str) -> Decimal | None:
    # Watermark letters can sit inside the number ("Rs.D 3,180.55", "47D5,735.30"): keep digits and dots only.
    return _parse_amount(re.sub(r"[^0-9.]", "", cell).lstrip("."))


def _parse_table_row(
    cells: list[str], cols: dict[str, int], day_first: bool
) -> ParsedTransaction | None:
    # Watermark letters/spaces can split the date ("22/01 /2024", "10-01-2H024"): drop letters, rejoin.
    date_txt = re.sub(r"\s*([/-])\s*", r"\1", re.sub(r"[^0-9/\- ]", "", cells[cols["date"]]))
    date_m = re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", date_txt)
    date = _parse_date(date_m.group(), day_first) if date_m else None
    if date is None:
        return None
    debit = _cell_amount(cells[cols["debit"]]) if "debit" in cols else None
    credit = _cell_amount(cells[cols["credit"]]) if "credit" in cols else None
    if debit is not None:
        amount, direction = debit, "debit"
    elif credit is not None:
        amount, direction = credit, "credit"
    elif "crdr" in cols and "amount" in cols:
        amount = _cell_amount(cells[cols["amount"]])
        marker = cells[cols["crdr"]].upper()
        direction = "credit" if "CR" in marker else "debit"
        if amount is None or not ("CR" in marker or "DR" in marker):
            return None
    else:
        return None
    desc = cells[cols["desc"]].strip() if "desc" in cols else ""
    return ParsedTransaction(date=date, description=desc, amount=amount, direction=direction)


def parse_statement(text: str) -> list[ParsedTransaction]:
    results: list[ParsedTransaction] = []
    day_first = _is_day_first(text)
    table_cols: dict[str, int] | None = None
    table_width = 0
    lines = text.splitlines()
    if any(_is_amount_header(ln) for ln in lines) and not any(
        (h := _header_columns([c.strip() for c in ln.split("|")])) and "balance" not in h
        for ln in lines
        if "|" in ln
    ):
        return _parse_blocks(text, day_first)
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Table rows (pdf_parser keeps empty cells): header row maps debit/credit columns
        if "|" in line:
            cells = [c.strip() for c in line.split("|")]
            header = _header_columns(cells)
            if header:
                table_cols, table_width = header, len(cells)
                continue
            if table_cols and len(cells) == table_width:
                tx = _parse_table_row(cells, table_cols, day_first)
                if tx:
                    results.append(tx)
                continue

        # Try pipe-delimited first
        m = _PIPE_RE.match(line)
        if m:
            date = _parse_date(m.group("date"), day_first)
            amount = _parse_amount(m.group("amount"))
            if date is None or amount is None or amount > _SKIP_AMOUNT:
                continue
            direction = _direction_from_token(m.group("dir"))
            raw_cat = m.group("cat")
            results.append(
                ParsedTransaction(
                    date=date,
                    description=m.group("desc").strip(),
                    amount=amount,
                    direction=direction,
                    category_name=raw_cat.strip() or None if raw_cat is not None else None,
                )
            )
            continue

        # Regex fallback: find amount in line (rightmost match — amount is last column)
        amt_match = None
        for m in _AMOUNT_RE.finditer(line):
            amt_match = m
        if not amt_match:
            continue
        amount = _parse_amount(amt_match.group(1))
        if amount is None or amount > _SKIP_AMOUNT:
            continue

        # Trailing - immediately after the amount → credit (payment)
        trailing_minus = amt_match.group(2) == "-"

        # Find date at start of line (try up to 20 chars)
        date = None
        date_end = 0
        for end in range(min(len(line), 20), 5, -1):
            date = _parse_date(line[:end], day_first)
            if date:
                date_end = end
                break

        if date is not None:
            # Skip a second date immediately after the first (posting date column)
            rest = line[date_end:].strip()
            for end in range(min(len(rest), 10), 4, -1):
                if _parse_date(rest[:end], day_first) is not None:
                    rest = rest[end:].strip()
                    break
            # Description: text between (second) date and amount, minus location noise
            pre_amt = rest[: rest.rfind(amt_match.group(1))].strip()
        else:
            # Description-first layout: numeric date anywhere before a decimal amount
            if "." not in amt_match.group(1):
                continue
            for dm in _DATE_ANYWHERE_RE.finditer(line):
                date = _parse_date(dm.group(), day_first)
                if date and dm.end() <= amt_match.start():
                    pre_amt = f"{line[: dm.start()]} {line[dm.end() : amt_match.start()]}".strip()
                    break
                date = None
            if date is None:
                continue
        pre_amt = _LOCATION_NOISE_RE.sub("", pre_amt).strip()
        desc = pre_amt or line

        # Direction: trailing - beats explicit DEBIT/CREDIT keyword
        if trailing_minus:
            direction = "credit"
        else:
            suffix = line[amt_match.end():].strip()
            dir_m = _DIR_RE.search(suffix)
            direction = _direction_from_token(dir_m.group(1)) if dir_m else "debit"

        results.append(
            ParsedTransaction(
                date=date,
                description=desc,
                amount=amount,
                direction=direction,
            )
        )

    return results
