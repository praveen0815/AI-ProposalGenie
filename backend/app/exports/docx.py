"""Editable Word proposals rendered with python-docx."""

import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from app.exports.document import ProposalDocument, section_body
from app.exports.pdf import ExportError


def render_docx(document: ProposalDocument) -> bytes:
    try:
        word = Document()
        _header_footer(word, document)
        brand = word.add_paragraph()
        _run(brand, document.company_name, bold=True, size=14, color="0E3A4D")
        if document.tagline:
            tagline = word.add_paragraph()
            _run(tagline, document.tagline, size=10, color="475569")
        title = word.add_heading(document.title, level=1)
        _paint(title, "0F172A")
        word.add_heading("Client", level=2)
        if document.client_lines:
            for line in document.client_lines:
                word.add_paragraph(line)
        else:
            word.add_paragraph("Client details were not recorded.")
        word.add_paragraph(f"Document date: {document.created_label}")
        if section_body(document.sections, "executive") is None:
            _heading_and_body(word, "Executive summary", document.summary)
        for section_title, body in document.sections:
            _heading_and_body(word, section_title, body)
        if section_body(document.sections, "deliverable") is None:
            _heading_and_body(word, "Deliverables", None)
        if section_body(document.sections, "timeline") is None:
            _heading_and_body(word, "Timeline", None)
        _budget(word, document)
        if section_body(document.sections, "terms") is None:
            _heading_and_body(word, "Terms and conditions", None)
        buffer = io.BytesIO()
        word.save(buffer)
    except Exception as exc:
        raise ExportError("DOCX rendering failed") from exc
    return buffer.getvalue()


def _heading_and_body(word: Document, title: str, body: str | None) -> None:
    word.add_heading(title, level=2)
    text = (body or "").strip()
    if not text:
        word.add_paragraph("This proposal does not include this section.")
        return
    for block in text.splitlines():
        word.add_paragraph(block if block.strip() else "")


def _budget(word: Document, document: ProposalDocument) -> None:
    word.add_heading("Budget breakdown", level=2)
    if not document.budgets:
        word.add_paragraph("No budget lines have been saved.")
        return
    for group in document.budgets:
        word.add_paragraph(f"Currency {group.currency}")
        word.add_paragraph(
            f"{group.confirmed_count} confirmed line(s), {group.estimated_count} estimated line(s). Estimated prices are not approved."
        )
        table = word.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        headers = ("Resource", "Quantity", "Unit price", "Source", "Subtotal")
        for cell, label in zip(table.rows[0].cells, headers, strict=True):
            cell.text = label
        for row in group.rows:
            cells = table.add_row().cells
            cells[0].text = f"{row.name} ({row.category})"
            cells[1].text = f"{row.quantity} {row.unit}"
            cells[2].text = row.unit_price
            cells[3].text = row.source
            cells[4].text = row.subtotal
        word.add_paragraph(
            f"Subtotal {group.base}. Discount {group.discount}. Tax {group.tax}. Grand total {group.grand_total} {group.currency}."
        )


def _header_footer(word: Document, document: ProposalDocument) -> None:
    section = word.sections[0]
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _run(header, document.company_name, bold=True, size=9, color="0E3A4D")
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _run(footer, f"Created {document.created_label}  ·  Page ", size=8, color="64748B")
    _page_field(footer)


def _page_field(paragraph) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instruction)
    run._r.append(end)


def _run(paragraph, text: str, *, bold: bool = False, size: int = 11, color: str = "1E293B") -> None:
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)


def _paint(paragraph, color: str) -> None:
    for run in paragraph.runs:
        run.font.color.rgb = RGBColor.from_string(color)
