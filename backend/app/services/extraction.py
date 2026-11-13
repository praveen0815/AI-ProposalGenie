"""Validate uploads and extract text from supported documents."""

import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath

from app.models.enums import DocumentFileType

MAX_PDF_PAGES = 200
MAX_DOCX_XML_BYTES = 20 * 1024 * 1024

_EXTENSIONS = {
    ".pdf": DocumentFileType.PDF,
    ".docx": DocumentFileType.DOCX,
    ".txt": DocumentFileType.TXT,
    ".md": DocumentFileType.MARKDOWN,
    ".markdown": DocumentFileType.MARKDOWN,
}

_CLIENT_MEDIA_TYPES = {
    DocumentFileType.PDF: {"application/pdf"},
    DocumentFileType.DOCX: {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    DocumentFileType.TXT: {"text/plain"},
    DocumentFileType.MARKDOWN: {"text/markdown", "text/x-markdown", "text/plain"},
}

_STORED_SUFFIX = {
    DocumentFileType.PDF: ".pdf",
    DocumentFileType.DOCX: ".docx",
    DocumentFileType.TXT: ".txt",
    DocumentFileType.MARKDOWN: ".md",
}


class RejectedUpload(Exception):
    """The upload failed validation before it was stored."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ExtractionFailed(Exception):
    """A stored file could not be turned into text."""


@dataclass(frozen=True)
class PreparedUpload:
    original_filename: str
    file_type: DocumentFileType
    suffix: str


@dataclass(frozen=True)
class ExtractedText:
    text: str
    page_count: int | None


def stored_suffix(file_type: DocumentFileType) -> str:
    return _STORED_SUFFIX[file_type]


def prepare_upload(filename: str | None, content_type: str | None, data: bytes) -> PreparedUpload:
    """Check the extension, the bytes, and any declared media type."""

    if not data:
        raise RejectedUpload(422, "The file is empty")

    original_filename, extension = _display_name(filename)
    declared = _EXTENSIONS.get(extension)
    if declared is None:
        raise RejectedUpload(415, "Upload a PDF, DOCX, TXT, or Markdown file")

    detected = _detect(data)
    if detected is None:
        raise RejectedUpload(422, "The file content does not match its extension")
    if declared in {DocumentFileType.TXT, DocumentFileType.MARKDOWN}:
        if detected != DocumentFileType.TXT:
            raise RejectedUpload(422, "The file content does not match its extension")
    elif detected != declared:
        raise RejectedUpload(422, "The file content does not match its extension")

    client_type = _client_media_type(content_type)
    if client_type is not None and client_type not in _CLIENT_MEDIA_TYPES[declared]:
        raise RejectedUpload(415, "The file content does not match the declared media type")

    return PreparedUpload(original_filename=original_filename, file_type=declared, suffix=_STORED_SUFFIX[declared])


def extract_text(file_type: DocumentFileType, data: bytes) -> ExtractedText:
    """Return normalized text or raise ExtractionFailed."""

    if file_type == DocumentFileType.PDF:
        extracted = _extract_pdf(data)
    elif file_type == DocumentFileType.DOCX:
        extracted = _extract_docx(data)
    else:
        extracted = _extract_plain_text(data)

    if not extracted.text.strip():
        raise ExtractionFailed("The file has no extractable text")
    return extracted


def _display_name(filename: str | None) -> tuple[str, str]:
    raw = (filename or "").replace("\\", "/")
    base = raw.split("/")[-1].strip()
    cleaned = "".join(character for character in base if character.isprintable() and character not in '<>:"|?*')
    cleaned = cleaned[:200]
    suffix = PurePosixPath(cleaned).suffix.lower()
    if suffix not in _EXTENSIONS:
        raise RejectedUpload(415, "Upload a PDF, DOCX, TXT, or Markdown file")
    stem = PurePosixPath(cleaned).stem.strip().strip(".")
    if not stem:
        stem = "document"
    return f"{stem}{suffix}"[:200], suffix


def _client_media_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    media = content_type.split(";", 1)[0].strip().lower()
    if media in {"", "application/octet-stream"}:
        return None
    return media


def _detect(data: bytes) -> DocumentFileType | None:
    if data.startswith(b"%PDF-"):
        return DocumentFileType.PDF
    if _is_docx(data):
        return DocumentFileType.DOCX
    if _is_text(data):
        return DocumentFileType.TXT
    return None


def _is_docx(data: bytes) -> bool:
    if not data.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                return False
            if archive.getinfo("word/document.xml").file_size > MAX_DOCX_XML_BYTES:
                raise RejectedUpload(422, "The document content is too large to process")
    except zipfile.BadZipFile:
        return False
    return True


def _is_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _extract_pdf(data: bytes) -> ExtractedText:
    import pymupdf

    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ExtractionFailed("The file could not be read") from exc

    try:
        if getattr(document, "needs_pass", False):
            raise ExtractionFailed("This PDF is password protected")
        if document.page_count > MAX_PDF_PAGES:
            raise ExtractionFailed(f"This PDF exceeds the {MAX_PDF_PAGES} page limit")
        pages = [page.get_text() for page in document]
        text = "\n".join(pages).strip()
        return ExtractedText(text=text, page_count=document.page_count)
    except ExtractionFailed:
        raise
    except Exception as exc:
        raise ExtractionFailed("The file could not be read") from exc
    finally:
        document.close()


def _extract_docx(data: bytes) -> ExtractedText:
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError

    try:
        document = Document(BytesIO(data))
        parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
    except (PackageNotFoundError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise ExtractionFailed("The file could not be read") from exc
    except Exception as exc:
        raise ExtractionFailed("The file could not be read") from exc
    return ExtractedText(text="\n".join(parts).strip(), page_count=None)


def _extract_plain_text(data: bytes) -> ExtractedText:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExtractionFailed("The file could not be read") from exc
    return ExtractedText(text=text.strip(), page_count=None)
