#!/usr/bin/env python3
"""
Analyze deviation between USD-pivot-derived cross-rates and Frankfurter's
own direct cross-rates, over the full ECB history (1999-01-04 → today).

Usage:
    python scripts/analyze_crossrate_deviation.py
    python scripts/analyze_crossrate_deviation.py --pairs EUR/GBP EUR/JPY
    python scripts/analyze_crossrate_deviation.py --out report.png
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import httpx
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

FRANKFURTER_BASE = "https://api.frankfurter.app"
START = "1999-01-04"  # ECB launch date; Frankfurter has no data before this
END = date.today().isoformat()

DEFAULT_PAIRS = [
    ("EUR", "GBP"),
    ("EUR", "JPY"),
    ("EUR", "CHF"),
    ("GBP", "JPY"),
    ("GBP", "CHF"),
]


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def fetch_series(base: str) -> pd.DataFrame:
    """Fetch full time-series for base→all currencies. Returns DataFrame indexed by date."""
    url = f"{FRANKFURTER_BASE}/{START}..{END}?from={base}"
    print(f"  Fetching {base}→all ({START}..{END}) …", end=" ", flush=True)
    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame.from_dict(data["rates"], orient="index")
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    print(f"{len(df)} dates, {len(df.columns)} currencies")
    return df


# ---------------------------------------------------------------------------
# Deviation analysis
# ---------------------------------------------------------------------------

def analyze_pair(
    usd_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    base: str,
    quote: str,
) -> pd.DataFrame:
    """
    Compare derived vs actual rates for base→quote.

    Derived:  actual_df[quote] (rates expressed from base already, since actual_df
              is fetched with from=base) — wait, we use the actual_df as truth.
    Derived:  usd_df[quote] / usd_df[base]  (USD-pivot cross-rate)
    Actual:   actual_df[quote]               (Frankfurter's direct base→quote)
    """
    derived = usd_df[quote] / usd_df[base]
    actual = actual_df[quote]

    common = derived.index.intersection(actual.index)
    derived = derived.loc[common]
    actual = actual.loc[common]

    abs_dev = (derived - actual).abs()
    rel_dev_pct = (abs_dev / actual) * 100

    return pd.DataFrame({
        "derived": derived,
        "actual": actual,
        "abs_deviation": abs_dev,
        "rel_deviation_pct": rel_dev_pct,
    })


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_summary(results: dict[str, pd.DataFrame]) -> None:
    rows = []
    for pair, df in results.items():
        s = df["rel_deviation_pct"]
        rows.append({
            "pair": pair,
            "n_dates": len(s),
            "mean_%": f"{s.mean():.6f}",
            "median_%": f"{s.median():.6f}",
            "max_%": f"{s.max():.6f}",
            "p99_%": f"{s.quantile(0.99):.6f}",
            "max_abs_date": str(df["abs_deviation"].idxmax().date()),
        })
    tbl = pd.DataFrame(rows).set_index("pair")
    print("\n=== Relative deviation summary (derived vs Frankfurter direct) ===")
    print(tbl.to_string())
    print()


def plot_results(results: dict[str, pd.DataFrame], out: str) -> None:
    n = len(results)
    fig, axes = plt.subplots(n, 2, figsize=(16, 3.5 * n))
    if n == 1:
        axes = [axes]

    fig.suptitle(
        f"USD-pivot cross-rate deviation vs Frankfurter direct  ({START} → {END})",
        fontsize=13,
        fontweight="bold",
    )

    for ax_row, (pair, df) in zip(axes, results.items()):
        ax_ts, ax_hist = ax_row

        # Time series
        ax_ts.plot(df.index, df["rel_deviation_pct"], linewidth=0.5, color="steelblue", alpha=0.8)
        ax_ts.axhline(df["rel_deviation_pct"].mean(), color="tomato", linewidth=1, linestyle="--", label="mean")
        ax_ts.set_title(f"{pair}  —  relative deviation (%)", fontsize=10)
        ax_ts.set_ylabel("% deviation")
        ax_ts.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.4f"))
        ax_ts.legend(fontsize=8)
        ax_ts.grid(True, alpha=0.3)

        # Histogram
        ax_hist.hist(df["rel_deviation_pct"], bins=80, color="steelblue", alpha=0.75, edgecolor="none")
        ax_hist.axvline(df["rel_deviation_pct"].mean(), color="tomato", linewidth=1.5, linestyle="--", label="mean")
        ax_hist.set_title(f"{pair}  —  distribution", fontsize=10)
        ax_hist.set_xlabel("% deviation")
        ax_hist.set_ylabel("count")
        ax_hist.legend(fontsize=8)
        ax_hist.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Plot saved → {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pairs",
        nargs="+",
        metavar="BASE/QUOTE",
        help="Currency pairs to analyse, e.g. EUR/GBP GBP/JPY",
    )
    parser.add_argument("--out", default="crossrate_deviation.png", help="Output plot filename")
    args = parser.parse_args()

    pairs: list[tuple[str, str]]
    if args.pairs:
        pairs = []
        for p in args.pairs:
            parts = p.upper().split("/")
            if len(parts) != 2:
                print(f"Invalid pair format: {p!r}  (expected BASE/QUOTE)", file=sys.stderr)
                sys.exit(1)
            pairs.append((parts[0], parts[1]))
    else:
        pairs = DEFAULT_PAIRS

    print("Fetching data from Frankfurter …")

    # Always need USD-base series for derivation
    usd_df = fetch_series("USD")

    # Fetch each unique base that appears in pairs (excluding USD, already have it)
    unique_bases = {base for base, _ in pairs if base != "USD"}
    base_dfs: dict[str, pd.DataFrame] = {"USD": usd_df}
    for base in unique_bases:
        base_dfs[base] = fetch_series(base)

    print("\nAnalysing …")
    results: dict[str, pd.DataFrame] = {}
    for base, quote in pairs:
        pair_label = f"{base}/{quote}"
        if base not in base_dfs:
            print(f"  Skipping {pair_label}: no data for base {base}")
            continue
        if quote not in usd_df.columns:
            print(f"  Skipping {pair_label}: {quote} not in USD series")
            continue
        if base != "USD" and quote not in base_dfs[base].columns:
            print(f"  Skipping {pair_label}: {quote} not in {base} series")
            continue
        df = analyze_pair(usd_df, base_dfs[base], base, quote)
        results[pair_label] = df
        print(f"  {pair_label}: {len(df)} dates analysed")

    if not results:
        print("No pairs could be analysed.", file=sys.stderr)
        sys.exit(1)

    print_summary(results)
    plot_results(results, args.out)


if __name__ == "__main__":
    main()
