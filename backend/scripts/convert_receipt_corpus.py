#!/usr/bin/env python3 -I
"""Convert FiftyOne-format receipt datasets into <stem>.<ext> + <stem>.expected.json.

Usage (run with -I; inputs are untrusted data, nothing from them is executed):
    python3 -I convert_receipt_corpus.py sroie SRC_DIR DST_DIR
    python3 -I convert_receipt_corpus.py cord  SRC_DIR DST_DIR

SRC_DIR holds samples.json and data/<files> (Voxel51/scanned_receipts for sroie,
Zarov888/consolidated_receipt_dataset for cord). Stdlib only.

Output format per sample:
  {"kind":"receipt","date":"YYYY-MM-DD"|null,"total":"123.45"|null,
   "currency":"MYR"|"IDR"|null,"merchant":"..."|null}

Rules: totals become plain decimal strings (currency symbols and thousands
separators stripped, value otherwise untouched). Dates become ISO only when
unambiguous, else null (counted). Nothing is invented. Currency is a
dataset-level constant (SROIE = Malaysian receipts, CORD = Indonesian receipts).
"""

import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def _iso(y, m, d):
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def parse_date(raw):
    """Return ISO date or None when ambiguous/unparseable."""
    if not isinstance(raw, str):
        return None
    s = raw.strip().strip("()").strip().upper()
    if not s:
        return None
    # YYYY-MM-DD, YYYY/MM/DD (year first: unambiguous)
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return _iso(int(m[1]), int(m[2]), int(m[3]))
    # DD MON YYYY / DD-MON-YYYY / DD/MON/YYYY (month name)
    m = re.fullmatch(r"(\d{1,2})[ /-]([A-Z]{3})[ /-](\d{4})", s)
    if m and m[2] in MONTHS:
        return _iso(int(m[3]), MONTHS[m[2]], int(m[1]))
    # MON D, YYYY
    m = re.fullmatch(r"([A-Z]{3}) (\d{1,2}), (\d{4})", s)
    if m and m[1] in MONTHS:
        return _iso(int(m[3]), MONTHS[m[1]], int(m[2]))
    # numeric, 4-digit year last: DD/MM/YYYY vs MM/DD/YYYY
    m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s)
    if not m:
        m = re.fullmatch(r"(\d{2})(\d{2})(\d{4})", s)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        if a == b:
            return _iso(y, a, b)
        if a > 12 >= b:
            return _iso(y, b, a)
        if b > 12 >= a:
            return _iso(y, a, b)
        return None
    # 2-digit year numerics, dotted forms, anything else: ambiguous -> null
    return None


def parse_total(raw):
    """Return a plain decimal string or None. Keeps the source value."""
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    s = re.sub(r"(?i)^(rp\.?|rm|total|\$)\s*", "", s).strip()
    s = re.sub(r"(?i)^(rp\.?|rm|\$)\s*", "", s).strip()
    if not re.fullmatch(r"-?[\d.,]+", s) or not re.search(r"\d", s):
        return None
    neg = s.startswith("-")
    body = s.lstrip("-")
    out = None
    seps = [c for c in body if c in ".,"]
    if not seps:
        out = body
    elif "." in body and "," in body:
        dec = body[max(body.rfind("."), body.rfind(","))]
        thou = "," if dec == "." else "."
        head, _, frac = body.rpartition(dec)
        groups = head.split(thou)
        ok = (
            dec not in head
            and 1 <= len(groups[0]) <= 3
            and all(len(g) == 3 for g in groups[1:])
            and frac.isdigit()
            and 1 <= len(frac) <= 2
            and groups[0] != ""
        )
        if ok:
            out = "".join(groups) + "." + frac
    else:
        sep = seps[0]
        parts = body.split(sep)
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            # thousands grouping only
            if 1 <= len(parts[0]) <= 3 and parts[0] != "" and all(len(p) == 3 for p in parts[1:]):
                out = "".join(parts)
        elif len(parts) == 2 and parts[0] != "" and 1 <= len(parts[1]) <= 2:
            out = parts[0] + "." + parts[1]
        elif len(parts) == 2 and parts[0] != "" and len(parts[1]) > 3:
            # e.g. Rp 29000.00 handled above; 4+ decimals is ambiguous
            out = None
    if out is None or not re.fullmatch(r"\d+(\.\d+)?", out):
        return None
    return ("-" if neg else "") + out


def write_sample(src_root, dst, sample, exp):
    rel = Path(sample["filepath"])
    src = src_root / rel
    if not src.is_file():
        return False
    shutil.copyfile(src, dst / (rel.stem + rel.suffix.lower()))
    (dst / (rel.stem + ".expected.json")).write_text(
        json.dumps(exp, ensure_ascii=False), encoding="utf-8"
    )
    return True


def main(argv):
    if len(argv) != 4 or argv[1] not in ("sroie", "cord"):
        print(__doc__)
        return 2
    kind, src_root, dst = argv[1], Path(argv[2]), Path(argv[3])
    dst.mkdir(parents=True, exist_ok=True)
    samples = json.loads((src_root / "samples.json").read_text(encoding="utf-8"))["samples"]
    n = missing = date_null = total_null = 0
    for s in samples:
        if kind == "sroie":
            merchant = (s.get("company") or "").strip() or None
            d, t, cur = parse_date(s.get("date")), parse_total(s.get("total")), "MYR"
            date_null += d is None
        else:
            merchant, d, cur = None, None, "IDR"  # mirror has no date/merchant field
            t = parse_total(s.get("total_price"))
        total_null += t is None
        exp = {"kind": "receipt", "date": d, "total": t, "currency": cur, "merchant": merchant}
        if write_sample(src_root, dst, s, exp):
            n += 1
        else:
            missing += 1
    print(
        f"{kind}: written={n} missing_image={missing} date_null={date_null} total_null={total_null}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
