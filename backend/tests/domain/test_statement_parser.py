from decimal import Decimal

from src.domain.services.statement_parser import parse_statement


def test_parse_pipe_delimited():
    r = parse_statement("01/05/2026 | GRAB FOOD | 150.00 | DEBIT")
    assert len(r) == 1
    assert r[0].description == "GRAB FOOD"
    assert r[0].amount == Decimal("150.00")
    assert r[0].direction == "debit"


def test_parse_pipe_credit():
    r = parse_statement("01/05/2026 | SALARY | 50000.00 | CREDIT")
    assert len(r) == 1
    assert r[0].direction == "credit"


def test_parse_regex_cr_suffix():
    r = parse_statement("01/05/2026  REFUND  500.00 CR")
    assert len(r) == 1
    assert r[0].direction == "credit"


def test_parse_skips_empty_lines():
    r = parse_statement("\n\n01/05/2026 | GRAB | 10.00 | DEBIT\n\n")
    assert len(r) == 1


def test_parse_multiple_date_formats():
    lines = [
        "05/01/2026 | A | 10.00 | DEBIT",
        "01-05-2026 | B | 20.00 | DEBIT",
    ]
    results = parse_statement("\n".join(lines))
    assert len(results) == 2


def test_parse_skips_huge_amount():
    r = parse_statement("01/05/2026 | BALANCE | 9999999.00 | DEBIT")
    assert len(r) == 0


def test_parse_empty_input():
    assert parse_statement("") == []


# Verbatim Tesseract output for frontend/tests/e2e/fixtures/tesseract_fixture.png (4+ digit amounts,
# and the 01/18/2024 date dropped by the confidence filter before the tesseract.py fix).
_TESSERACT_FIXTURE_RAW = (
    "BANK STATEMENT\n"
    "01/15/2024 GROCERY STORE 450.00 DEBIT\n"
    "01/16/2024 SALARY DEPOSIT 25000.00 CREDIT\n"
    "01/17/2024 ELECTRICITY BILL 1200.00 DEBIT\n"
    "INTERNET SUBSCRIPTION 299.00 DEBIT\n"
    "01/20/2024 ONLINE SHOP REFUND 850.00 CREDIT"
)


def test_parse_regex_four_plus_digit_amounts_without_commas():
    r = parse_statement(_TESSERACT_FIXTURE_RAW)
    assert [(t.date.strftime("%Y-%m-%d"), t.amount, t.description) for t in r] == [
        ("2024-01-15", Decimal("450.00"), "GROCERY STORE"),
        ("2024-01-16", Decimal("25000.00"), "SALARY DEPOSIT"),
        ("2024-01-17", Decimal("1200.00"), "ELECTRICITY BILL"),
        ("2024-01-20", Decimal("850.00"), "ONLINE SHOP REFUND"),
    ]


def test_parse_tesseract_fixture_all_five_rows():
    text = _TESSERACT_FIXTURE_RAW.replace("INTERNET", "01/18/2024 INTERNET")
    r = parse_statement(text)
    assert [(t.date.strftime("%Y-%m-%d"), t.amount, t.description) for t in r] == [
        ("2024-01-15", Decimal("450.00"), "GROCERY STORE"),
        ("2024-01-16", Decimal("25000.00"), "SALARY DEPOSIT"),
        ("2024-01-17", Decimal("1200.00"), "ELECTRICITY BILL"),
        ("2024-01-18", Decimal("299.00"), "INTERNET SUBSCRIPTION"),
        ("2024-01-20", Decimal("850.00"), "ONLINE SHOP REFUND"),
    ]
