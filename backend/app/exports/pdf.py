"""PDF proposals rendered with ReportLab."""

import io
import re
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.exports.document import BudgetGroup, ProposalDocument, section_body

_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_REGISTERED = False


class ExportError(Exception):
    """The file could not be built. The message is not returned to clients."""


def render_pdf(document: ProposalDocument) -> bytes:
    _ensure_fonts()
    buffer = io.BytesIO()
    try:
        pdf = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=22 * mm,
            bottomMargin=18 * mm,
            title=document.title,
            author=document.company_name,
        )
        pdf.build(
            _story(document),
            onFirstPage=lambda canvas, doc: _chrome(canvas, doc, document),
            onLaterPages=lambda canvas, doc: _chrome(canvas, doc, document),
        )
    except Exception as exc:
        raise ExportError("PDF rendering failed") from exc
    return buffer.getvalue()


def _ensure_fonts() -> None:
    global _FONT, _FONT_BOLD, _REGISTERED
    if _REGISTERED:
        return
    regular = Path(r"C:\Windows\Fonts\arial.ttf")
    bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if regular.is_file() and bold.is_file():
        pdfmetrics.registerFont(TTFont("ProposalSans", str(regular)))
        pdfmetrics.registerFont(TTFont("ProposalSans-Bold", str(bold)))
        _FONT = "ProposalSans"
        _FONT_BOLD = "ProposalSans-Bold"
    _REGISTERED = True


def _story(document: ProposalDocument) -> list:
    styles = _styles()
    story: list = [
        Paragraph(_xml(document.company_name), styles["brand"]),
        Paragraph(_xml(document.tagline or "Proposal"), styles["tagline"]),
        Spacer(1, 8),
        Paragraph(_xml(document.title), styles["title"]),
        Spacer(1, 6),
        Paragraph("Prepared for", styles["label"]),
    ]
    if document.client_lines:
        story.extend(Paragraph(_xml(line), styles["body"]) for line in document.client_lines)
    else:
        story.append(Paragraph("Client details were not recorded.", styles["muted"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Document date: {_xml(document.created_label)}", styles["muted"]))
    story.append(Spacer(1, 12))
    if section_body(document.sections, "executive") is None:
        story.extend(_section("Executive summary", document.summary, styles))
    for title, body in document.sections:
        story.extend(_section(title, body, styles))
    story.extend(_missing(document, "Deliverables", "deliverable", styles))
    story.extend(_missing(document, "Timeline", "timeline", styles))
    story.extend(_budget(document.budgets, styles))
    story.extend(_missing(document, "Terms and conditions", "terms", styles))
    return story


def _missing(document: ProposalDocument, title: str, needle: str, styles: dict) -> list:
    if section_body(document.sections, needle) is not None:
        return []
    return _section(title, None, styles)


def _section(title: str, body: str | None, styles: dict) -> list:
    flow = [Paragraph(_xml(title), styles["heading"])]
    text = (body or "").strip()
    if not text:
        flow.append(Paragraph("This proposal does not include this section.", styles["muted"]))
        return flow
    for block in re.split(r"\n{2,}", text):
        lines = "<br/>".join(_xml(line) for line in block.splitlines() if line.strip())
        if lines:
            flow.append(Paragraph(lines, styles["body"]))
    return flow


def _budget(groups: tuple[BudgetGroup, ...], styles: dict) -> list:
    flow = [Paragraph("Budget breakdown", styles["heading"])]
    if not groups:
        flow.append(Paragraph("No budget lines have been saved.", styles["muted"]))
        return flow
    for group in groups:
        flow.append(Paragraph(f"Currency {_xml(group.currency)}", styles["label"]))
        flow.append(Paragraph(
            f"{group.confirmed_count} confirmed line(s), {group.estimated_count} estimated line(s). Estimated prices are not approved.",
            styles["muted"],
        ))
        header = ["Resource", "Qty", "Unit price", "Source", "Subtotal"]
        data = [[Paragraph(_xml(item), styles["table_header"]) for item in header]]
        for row in group.rows:
            data.append(
                [
                    Paragraph(_xml(f"{row.name} ({row.category})"), styles["table"]),
                    Paragraph(_xml(f"{row.quantity} {row.unit}"), styles["table"]),
                    Paragraph(_xml(row.unit_price), styles["table"]),
                    Paragraph(_xml(row.source), styles["table"]),
                    Paragraph(_xml(row.subtotal), styles["table"]),
                ]
            )
        table = Table(data, colWidths=[62 * mm, 28 * mm, 28 * mm, 28 * mm, 28 * mm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0E3A4D")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), white),
                    ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
                    ("BACKGROUND", (0, 1), (-1, -1), HexColor("#F8FAFC")),
                    ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        flow.extend([table, Spacer(1, 6), Paragraph(
            f"Subtotal {group.base} · Discount {group.discount} · Tax {group.tax} · Grand total {group.grand_total} {group.currency}",
            styles["body"],
        )])
    return flow


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "brand": ParagraphStyle("brand", fontName=_FONT_BOLD, fontSize=11, textColor=HexColor("#0E3A4D"), alignment=TA_LEFT),
        "tagline": ParagraphStyle("tagline", fontName=_FONT, fontSize=9, textColor=HexColor("#475569"), spaceAfter=4),
        "title": ParagraphStyle("title", fontName=_FONT_BOLD, fontSize=20, leading=24, textColor=HexColor("#0F172A"), spaceAfter=6),
        "heading": ParagraphStyle("heading", fontName=_FONT_BOLD, fontSize=13, leading=16, textColor=HexColor("#0E3A4D"), spaceBefore=12, spaceAfter=4),
        "label": ParagraphStyle("label", fontName=_FONT_BOLD, fontSize=9, textColor=HexColor("#334155"), spaceBefore=4),
        "body": ParagraphStyle("body", fontName=_FONT, fontSize=10, leading=14, textColor=HexColor("#1E293B"), spaceAfter=4),
        "muted": ParagraphStyle("muted", fontName=_FONT, fontSize=9, leading=12, textColor=HexColor("#64748B"), spaceAfter=4),
        "table": ParagraphStyle("table", fontName=_FONT, fontSize=8, leading=10, textColor=HexColor("#0F172A")),
        "table_header": ParagraphStyle("table_header", fontName=_FONT_BOLD, fontSize=8, leading=10, textColor=white),
    }


def _chrome(canvas, doc, document: ProposalDocument) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(_brand_color(document.color))
    canvas.rect(0, height - 12 * mm, width, 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont(_FONT_BOLD, 9)
    canvas.drawString(16 * mm, height - 8 * mm, document.company_name[:70])
    if document.logo:
        try:
            canvas.drawImage(
            ImageReader(io.BytesIO(document.logo)),
            width - 28 * mm,
            height - 10 * mm,
            width=8 * mm,
            height=8 * mm,
            mask="auto",
            preserveAspectRatio=True,
        )
        except Exception:
            pass
    canvas.setFillColor(HexColor("#64748B"))
    canvas.setFont(_FONT, 8)
    canvas.drawString(16 * mm, 8 * mm, f"Created {document.created_label}")
    canvas.drawRightString(width - 16 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _brand_color(value: str) -> HexColor:
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        return HexColor(value)
    return HexColor("#0E3A4D")


def _xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
