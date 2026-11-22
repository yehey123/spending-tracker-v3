"""Convert AgamiAI Indian-Bank-Statements ground truth (*.src.json) to *.expected.json.

Usage: python3 -I convert_external_corpus.py <dir>
Pure stdlib; reads JSON only. Skips failed (zero-amount) rows. Warns if
opening + credits - debits != closing balance (source data has seeded anomalies).
"""

import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path


def iso(s: str) -> str:
    if "/" in s:
        return datetime.strptime(s, "%d/%m/%Y").strftime("%Y-%m-%d")
    return s[:10]


def convert(src: Path) -> dict:
    j = json.loads(src.read_text(), parse_float=Decimal)
    rows = []
    for t in j["transactions"]:
        if t.get("failed"):
            continue
        if "cr_dr" in t:
            amt, d = t["transaction_amount"], {"DR": "debit", "CR": "credit"}[t["cr_dr"]]
        elif t.get("debit"):
            amt, d = t["debit"], "debit"
        elif t.get("credit"):
            amt, d = t["credit"], "credit"
        else:
            continue
        if amt == 0:
            continue
        rows.append({"date": iso(t["date"]), "amount": f"{amt:.2f}", "direction": d})
    deb = sum((Decimal(r["amount"]) for r in rows if r["direction"] == "debit"), Decimal(0))
    cre = sum((Decimal(r["amount"]) for r in rows if r["direction"] == "credit"), Decimal(0))
    if j["opening_balance"] + cre - deb != j["closing_balance"]:
        print(
            f"WARN {src.name}: opening+credits-debits != closing (source balance anomaly)",
            file=sys.stderr,
        )
    return {"rows": rows, "total_debits": f"{deb:.2f}", "total_credits": f"{cre:.2f}"}


if __name__ == "__main__":
    for src in sorted(Path(sys.argv[1]).glob("*.src.json")):
        out = src.with_name(src.name.replace(".src.json", ".expected.json"))
        if not src.with_name(src.name.replace(".src.json", ".pdf")).exists():
            continue
        out.write_text(json.dumps(convert(src), indent=1))
        print("wrote", out.name)
