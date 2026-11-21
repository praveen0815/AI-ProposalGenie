"""Money math for proposal estimates. Totals use Decimal, never binary floats."""

from decimal import Decimal, ROUND_HALF_UP

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def line_amounts(
    quantity: Decimal,
    unit_price: Decimal,
    duration: Decimal,
    tax_percent: Decimal,
    discount_percent: Decimal,
) -> dict[str, Decimal]:
    """Return base, discount, tax, and subtotal for one resource line."""

    base = money(quantity * unit_price * duration)
    discount = money(base * discount_percent / Decimal(100))
    after_discount = money(base - discount)
    tax = money(after_discount * tax_percent / Decimal(100))
    return {
        "base": base,
        "discount": discount,
        "tax": tax,
        "subtotal": money(after_discount + tax),
    }


def sheet_totals(lines: list[dict[str, Decimal]]) -> dict[str, Decimal]:
    return {
        "base": money(sum((line["base"] for line in lines), ZERO)),
        "discount": money(sum((line["discount"] for line in lines), ZERO)),
        "tax": money(sum((line["tax"] for line in lines), ZERO)),
        "grand_total": money(sum((line["subtotal"] for line in lines), ZERO)),
    }
