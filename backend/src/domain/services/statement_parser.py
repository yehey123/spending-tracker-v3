from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import re


@dataclass
class ParsedTransaction:
    date: datetime
    description: str
    amount: Decimal
    direction: str  # "debit" | "credit"


_DATE_FORMATS = [
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%b %d",
]

_PIPE_RE = re.compile(
    r"^\s*(?P<date>[^|]+?)\s*\|\s*(?P<desc>[^|]+?)\s*\|\s*(?P<amount>[^|]+?)\s*\|\s*(?P<dir>[^|]+?)\s*$",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r"\d{1,3}(?:,\d{3})*(?:\.\d{2})?")
_DIR_RE = re.compile(r"\b(CR|CREDIT|DR|DEBIT)\b", re.IGNORECASE)
_SKIP_AMOUNT = Decimal("999999")


def _parse_date(s: str) -> datetime | None:
    s = s.strip()
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
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


def parse_statement(text: str) -> list[ParsedTransaction]:
    results: list[ParsedTransaction] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Try pipe-delimited first
        m = _PIPE_RE.match(line)
        if m:
            date = _parse_date(m.group("date"))
            amount = _parse_amount(m.group("amount"))
            if date is None or amount is None or amount > _SKIP_AMOUNT:
                continue
            direction = _direction_from_token(m.group("dir"))
            results.append(ParsedTransaction(date=date, description=m.group("desc").strip(), amount=amount, direction=direction))
            continue

        # Regex fallback: find amount in line
        amt_match = _AMOUNT_RE.search(line)
        if not amt_match:
            continue
        amount = _parse_amount(amt_match.group())
        if amount is None or amount > _SKIP_AMOUNT:
            continue

        # Find date at start of line
        # Try up to first 15 chars as date
        date = None
        for end in range(min(len(line), 20), 5, -1):
            date = _parse_date(line[:end])
            if date:
                break
        if date is None:
            continue

        # Description: text between date and amount
        pre_amt = line[: amt_match.start()].strip()
        desc = re.sub(r"^\S+\s+", "", pre_amt).strip() or pre_amt

        # Direction hint from suffix after amount
        suffix = line[amt_match.end():].strip()
        dir_m = _DIR_RE.search(suffix)
        direction = _direction_from_token(dir_m.group(1)) if dir_m else "debit"

        results.append(ParsedTransaction(date=date, description=desc, amount=amount, direction=direction))

    return results
