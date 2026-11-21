"""Decimal cost totals."""

from decimal import Decimal

from app.proposals.costing import line_amounts, sheet_totals


def test_line_applies_duration_discount_and_tax_without_float_error() -> None:
    amounts = line_amounts(
        Decimal("2"),
        Decimal("100"),
        Decimal("3"),
        Decimal("10"),
        Decimal("5"),
    )

    assert amounts == {
        "base": Decimal("600.00"),
        "discount": Decimal("30.00"),
        "tax": Decimal("57.00"),
        "subtotal": Decimal("627.00"),
    }
    assert all(isinstance(value, Decimal) for value in amounts.values())


def test_sheet_totals_sum_lines() -> None:
    first = line_amounts(Decimal("2"), Decimal("100"), Decimal("3"), Decimal("10"), Decimal("5"))
    second = line_amounts(Decimal("1"), Decimal("50"), Decimal("1"), Decimal("0"), Decimal("0"))

    totals = sheet_totals([first, second])

    assert totals["grand_total"] == Decimal("677.00")
    assert totals["discount"] == Decimal("30.00")
    assert totals["tax"] == Decimal("57.00")
