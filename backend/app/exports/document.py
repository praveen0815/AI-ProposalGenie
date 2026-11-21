"""Shared content for PDF and DOCX proposal documents."""

from dataclasses import dataclass


def section_body(sections: tuple[tuple[str, str], ...], needle: str) -> str | None:
    for title, body in sections:
        if needle in title.lower():
            return body
    return None


@dataclass(frozen=True)
class BudgetRow:
    name: str
    category: str
    quantity: str
    unit: str
    unit_price: str
    duration: str
    tax_percent: str
    discount_percent: str
    source: str
    subtotal: str


@dataclass(frozen=True)
class BudgetGroup:
    currency: str
    rows: tuple[BudgetRow, ...]
    base: str
    discount: str
    tax: str
    grand_total: str
    estimated_count: int
    confirmed_count: int


@dataclass(frozen=True)
class ProposalDocument:
    company_name: str
    tagline: str | None
    color: str
    logo: bytes | None
    title: str
    client_lines: tuple[str, ...]
    summary: str | None
    sections: tuple[tuple[str, str], ...]
    budgets: tuple[BudgetGroup, ...]
    created_label: str
