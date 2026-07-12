import pytest
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
