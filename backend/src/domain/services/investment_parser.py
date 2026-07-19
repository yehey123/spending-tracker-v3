"""Parse brokerage statement text for investment transactions.

Lines are expected to contain: SYMBOL, direction keyword (buy/bought/sell/sold),
share count, and a dollar price. Lines that cannot be parsed are collected as errors.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass
class ParsedInvestmentRow:
    symbol: str
    direction: str      # 'buy' | 'sell'
    shares: Decimal
    price: Decimal
    amount: Decimal
    commission: Decimal | None = None


TICKER_RE = re.compile(r'\b([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b')
BUY_RE = re.compile(r'\b(buy|bought|purchase)\b', re.IGNORECASE)
SELL_RE = re.compile(r'\b(sell|sold)\b', re.IGNORECASE)
SHARES_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:shs?|shares?)?', re.IGNORECASE)
PRICE_RE = re.compile(r'\$\s*([\d,]+\.?\d*)')
COMMISSION_RE = re.compile(r'(?:commission|fee|comm)[:\s]+\$\s*([\d,]+\.?\d*)', re.IGNORECASE)


def parse_investment_rows(text: str) -> tuple[list[ParsedInvestmentRow], list[dict]]:
    """Returns (parsed_rows, parse_errors). parse_errors is list of {raw_line, reason}."""
    rows: list[ParsedInvestmentRow] = []
    errors: list[dict] = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        ticker_m = TICKER_RE.search(line)
        price_m = PRICE_RE.search(line)
        if not ticker_m or not price_m:
            errors.append({"raw_line": line, "reason": "missing_symbol_or_price"})
            continue

        if BUY_RE.search(line):
            direction = 'buy'
        elif SELL_RE.search(line):
            direction = 'sell'
        else:
            errors.append({"raw_line": line, "reason": "missing_direction"})
            continue

        shares_m = SHARES_RE.search(line)
        if not shares_m:
            errors.append({"raw_line": line, "reason": "missing_shares"})
            continue

        try:
            shares = Decimal(shares_m.group(1))
            price = Decimal(price_m.group(1).replace(',', ''))
            amount = shares * price
        except (InvalidOperation, Exception) as exc:
            errors.append({"raw_line": line, "reason": str(exc)})
            continue

        commission: Decimal | None = None
        comm_m = COMMISSION_RE.search(line)
        if comm_m:
            try:
                commission = Decimal(comm_m.group(1).replace(',', ''))
            except InvalidOperation:
                pass

        rows.append(ParsedInvestmentRow(
            symbol=ticker_m.group(1),
            direction=direction,
            shares=shares,
            price=price,
            amount=amount,
            commission=commission,
        ))

    return rows, errors
