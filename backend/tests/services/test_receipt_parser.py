from datetime import datetime
from decimal import Decimal

from src.domain.services.receipt_parser import detect_kind, parse_receipt

MYR_RECEIPT = """BOOK TA .K (TAMAN DAYA) SDN BHD
NO 5 JALAN SAGU
25/12/2018 10:31
BOOK A        1  8.50
SUBTOTAL      9.00
TOTAL         9.00
CASH         10.00
CHANGE        1.00
"""

IDR_RECEIPT = """TOKO MAJU
Nasi Goreng 2x  40.000
SUBTOTAL        57.000
TOTAL           57.000
TUNAI          100.000
KEMBALI         43.000
"""

STATEMENT = """CREDIT CARD STATEMENT
Statement period 01/01/2026 - 31/01/2026
05/01/2026 GROCERY STORE MAKATI PH 1,234.50
07/01/2026 COFFEE SHOP PASIG PH 150.00
09/01/2026 ONLINE PAYMENT 2,000.00 CR
Total Debits 1,384.50
"""


def test_total_prefers_total_over_subtotal_and_ignores_change():
    assert parse_receipt(MYR_RECEIPT).total == Decimal("9.00")


def test_total_ignores_subtotal_when_it_comes_after_total():
    text = "SHOP\nTOTAL 20.00\nSUBTOTAL 18.00\nCHANGE 5.00\n"
    assert parse_receipt(text).total == Decimal("20.00")


def test_idr_thousands_separator():
    assert parse_receipt(IDR_RECEIPT).total == Decimal("57000")
    assert parse_receipt("TOTAL 1,591,600\n").total == Decimal("1591600")


def test_date_dd_mm_yyyy():
    assert parse_receipt(MYR_RECEIPT).date == datetime(2018, 12, 25)


def test_date_named_month():
    assert parse_receipt("SHOP\n25 Dec 2018\nTOTAL 1.00\n").date == datetime(2018, 12, 25)


def test_date_dd_mm_yy_dashes():
    assert parse_receipt("SHOP\n05-03-19\nTOTAL 1.00\n").date == datetime(2019, 3, 5)


def test_merchant_is_first_top_line():
    assert parse_receipt(MYR_RECEIPT).merchant == "BOOK TA .K (TAMAN DAYA) SDN BHD"


def test_detect_kind():
    assert detect_kind(STATEMENT) == "statement"
    assert detect_kind(MYR_RECEIPT) == "receipt"
    assert detect_kind(IDR_RECEIPT) == "receipt"
