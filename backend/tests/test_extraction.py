"""File validation and text extraction."""

import zipfile
from io import BytesIO

import pytest

from app.models.enums import DocumentFileType
from app.services.extraction import ExtractionFailed, RejectedUpload, extract_text, prepare_upload


def _pdf(text: str) -> bytes:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    payload = document.tobytes()
    document.close()
    return payload


def _docx(text: str) -> bytes:
    from docx import Document

    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_pdf_and_docx_extraction() -> None:
    pdf = prepare_upload("overview.pdf", "application/pdf", _pdf("Proposal facts"))
    docx = prepare_upload("overview.docx", None, _docx("Service catalog"))

    assert pdf.file_type is DocumentFileType.PDF
    assert extract_text(pdf.file_type, _pdf("Proposal facts")).text == "Proposal facts"
    assert extract_text(docx.file_type, _docx("Service catalog")).text == "Service catalog"


def test_text_and_markdown_extraction() -> None:
    text = prepare_upload("notes.txt", "text/plain; charset=utf-8", b"Plain notes")
    markdown = prepare_upload("guide.markdown", "text/markdown", b"# Guide\n\nDetails")

    assert text.file_type is DocumentFileType.TXT
    assert markdown.file_type is DocumentFileType.MARKDOWN
    assert extract_text(markdown.file_type, b"# Guide\n\nDetails").text.startswith("# Guide")


def test_path_is_removed_from_the_stored_display_name() -> None:
    prepared = prepare_upload("../../secret\\notes.txt", None, b"Safe name")

    assert prepared.original_filename == "notes.txt"


def test_empty_whitespace_and_unsupported_files_are_rejected() -> None:
    with pytest.raises(RejectedUpload) as empty:
        prepare_upload("empty.txt", "text/plain", b"")
    assert empty.value.status_code == 422

    with pytest.raises(ExtractionFailed, match="no extractable text"):
        extract_text(DocumentFileType.TXT, b"  \n\t")

    with pytest.raises(RejectedUpload) as unsupported:
        prepare_upload("image.png", "image/png", b"\x89PNG\r\n")
    assert unsupported.value.status_code == 415


def test_extension_and_declared_type_must_match_the_bytes() -> None:
    with pytest.raises(RejectedUpload) as mismatch:
        prepare_upload("notes.pdf", "application/pdf", b"this is plain text")
    assert mismatch.value.status_code == 422

    with pytest.raises(RejectedUpload) as media:
        prepare_upload("notes.txt", "application/pdf", b"this is plain text")
    assert media.value.status_code == 415


def test_corrupt_pdf_and_docx_fail_extraction() -> None:
    with pytest.raises(ExtractionFailed):
        extract_text(DocumentFileType.PDF, b"%PDF-1.7\nthis is not a pdf")

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", "not xml")
    with pytest.raises(ExtractionFailed):
        extract_text(DocumentFileType.DOCX, buffer.getvalue())
