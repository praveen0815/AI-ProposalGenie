"""Load extracted company documents into page-sized pieces."""

from dataclasses import dataclass

from app.models.knowledge import KnowledgeDocument


@dataclass(frozen=True)
class LoadedPage:
    page_number: int | None
    text: str


def load_pages(document: KnowledgeDocument) -> list[LoadedPage]:
    """Split stored text on PDF page breaks. Other files are a single body."""

    raw = document.extracted_text or ""
    if not raw.strip():
        return []
    if "\f" not in raw:
        return [LoadedPage(page_number=None, text=raw)]

    pages: list[LoadedPage] = []
    for number, page in enumerate(raw.split("\f"), start=1):
        if page.strip():
            pages.append(LoadedPage(page_number=number, text=page))
    return pages
