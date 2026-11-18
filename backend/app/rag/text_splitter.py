"""Clean extracted text and split it into overlapping chunks."""

import re
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.document_loader import LoadedPage

_BLANK_LINES = re.compile(r"\n{3,}")
_SPACES = re.compile(r"[ \t]{2,}")


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    page_number: int | None
    source: str


def clean_text(value: str) -> str:
    """Normalize whitespace without changing the words."""

    without_nulls = value.replace("\x00", "").replace("\t", " ")
    normalized = without_nulls.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = _SPACES.sub(" ", normalized)
    lines = [line.strip() for line in collapsed.split("\n")]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def split_pages(filename: str, pages: list[LoadedPage], chunk_size: int, chunk_overlap: int) -> list[TextChunk]:
    """Attach filename and page metadata to each chunk."""

    if not pages:
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    documents = []
    for page in pages:
        text = clean_text(page.text)
        if not text:
            continue
        metadata = {"page_number": page.page_number} if page.page_number is not None else {}
        documents.append(Document(page_content=text, metadata=metadata))
    if not documents:
        return []
    chunks: list[TextChunk] = []
    for part in splitter.split_documents(documents):
        text = part.page_content.strip()
        if not text:
            continue
        page_number = part.metadata.get("page_number")
        page = page_number if isinstance(page_number, int) else None
        source = f"{filename} p.{page}" if page else filename
        chunks.append(TextChunk(index=len(chunks), text=text, page_number=page, source=source))
    return chunks
