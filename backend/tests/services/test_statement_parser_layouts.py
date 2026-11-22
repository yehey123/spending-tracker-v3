"""Non-AI statement parser — layout C, DD/MM inference, debit/credit column tables."""

from datetime import datetime
from decimal import Decimal

from src.domain.services.statement_parser import parse_statement


def _key(t):
    return (t.date.month, t.date.day, t.amount, t.direction)


def test_layout_c_description_before_date():
    text = (
        "Description Date Amount\n"
        "GRAB* TRIP 14/10/2026 10,374.77\n"
        "PAYMENT THANK YOU 18/10/2026 1,013.10-\n"
    )
    parsed = parse_statement(text)
    assert [_key(t) for t in parsed] == [
        (10, 14, Decimal("10374.77"), "debit"),
        (10, 18, Decimal("1013.10"), "credit"),
    ]
    assert parsed[0].description == "GRAB* TRIP"


def test_slash_dates_infer_day_first_from_statement():
    text = "BAYANIHAN BOOKSTORE 05/10/2026 12,262.57\nGRAB* TRIP 14/10/2026 10,374.77\n"
    parsed = parse_statement(text)
    assert [(t.date.month, t.date.day) for t in parsed] == [(10, 5), (10, 14)]


def test_slash_dates_infer_month_first_from_statement():
    text = "10/02/2026 MANGO TREE 4,610.17\n10/14/2026 JOLLIBEE 5,859.08\n"
    parsed = parse_statement(text)
    assert [(t.date.month, t.date.day) for t in parsed] == [(10, 2), (10, 14)]


def test_debit_credit_columns_map_direction_and_ignore_balance():
    text = (
        "Txn Date | Value Date | Description | Debit | Credit | Balance\n"
        "01-01-2024 | 01 Jan 2024 | NEFT Cr-1 CLOTHING | | Rs. 6,086.63 | Rs. 65,218.35\n"
        "02-01-2024 | 02 Jan 2024 | Chq Paid KAUSHIK | Rs. 23,702.04 | | Rs. 41,516.31\n"
    )
    parsed = parse_statement(text)
    assert [(t.date, t.amount, t.direction) for t in parsed] == [
        (datetime(2024, 1, 1), Decimal("6086.63"), "credit"),
        (datetime(2024, 1, 2), Decimal("23702.04"), "debit"),
    ]


def test_cr_dr_column_with_day_first_dates_and_large_amount():
    text = (
        "No. | Value Date | Description | Cr/Dr | Transaction Amount | Available Balance\n"
        "1 | 13/01/2024 | RTGS-abc | DR | 4,753,862.25 | 803,454.76\n"
        "2 | 02/01/2024 | IMPS-xyz | CR | 101,795.99 | 905,250.75\n"
    )
    parsed = parse_statement(text)
    assert [(t.date.month, t.date.day, t.amount, t.direction) for t in parsed] == [
        (1, 13, Decimal("4753862.25"), "debit"),
        (1, 2, Decimal("101795.99"), "credit"),
    ]


def test_pdf_cell_strips_watermark_letters():
    from src.domain.services.pdf_parser import _clean_cell

    assert _clean_cell("E\nH\nTDebit\nN") == "TDebit"
    assert _clean_cell("D\nE\n577725115") == "577725115"
    assert _clean_cell("01-01-2024\n11:30:55") == "01-01-2024 11:30:55"
    assert _clean_cell(None) == ""


def _txs(text):
    return [(t.date.month, t.date.day, t.amount, t.direction) for t in parse_statement(text)]


def test_amount_balance_header_without_crdr_heading_uses_row_tokens():
    text = (
        "No. ID Date Posted Date Description Amount Balance\n"
        "$1 | 13/01/2024 | 13/01/2024 12:53:19 PM cR 104,999.07, 338,141.34\n"
        "$2 | 14/01/2024 | 14/01/2024 DR 5,000.00| 333,141.34\n"
    )
    assert _txs(text) == [
        (1, 13, Decimal("104999.07"), "credit"),
        (1, 14, Decimal("5000.00"), "debit"),
    ]


def test_wrapped_rows_description_above_and_below():
    text = (
        "ID Date Posted Date Description Amount Balance\n"
        "NEFT-287837415387-PRECISION\n"
        "$82878420 | 13/01/2024 | 13/01/2024 12:53:19 PM cR 104,999.07, 338,141.34\n"
        "WORK\n"
        "UPI/CR/725664555690/Srinivas\n"
        "17 | $82961328 | 14/01/2024 14/01/2024 Dr 252,626.61| 85,514.73\n"
        "Krishnan\n"
        "15/01/2024 15/01/2024\n"
        "cR 1,000.00\n"
        "2,000.00\n"
    )
    assert _txs(text) == [
        (1, 13, Decimal("104999.07"), "credit"),
        (1, 14, Decimal("252626.61"), "debit"),
        (1, 15, Decimal("1000.00"), "credit"),
    ]


def test_direction_falls_back_to_balance_change():
    text = (
        "ID Date Description Amount Balance\n"
        "1 | 13/01/2024 | A 100.00 1,100.00\n"
        "2 | 14/01/2024 | B 50.00 1,150.00\n"
    )
    assert [t[3] for t in _txs(text)][1] == "credit"


def test_lone_balance_figure_yields_amount_from_balance_change():
    text = (
        "ID Date Description Amount Balance\n"
        "1 | 13/01/2024 | A DR 100.00 1,000.00\n"
        "2 | 14/01/2024 | B 1,250.00\n"
    )
    assert _txs(text)[1] == (1, 14, Decimal("250.00"), "credit")
