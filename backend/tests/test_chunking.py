"""Text cleaning and chunk metadata."""

from app.rag.document_loader import LoadedPage
from app.rag.text_splitter import clean_text, split_pages


def test_clean_text_normalizes_whitespace() -> None:
    assert clean_text("Alpha\r\n\n\n  beta\tgamma") == "Alpha\n\nbeta gamma"


def test_chunks_keep_page_numbers_and_overlap() -> None:
    pages = [LoadedPage(page_number=1, text="A" * 80), LoadedPage(page_number=2, text="Enterprise support pricing is annual.")]
    chunks = split_pages("pricing.pdf", pages, chunk_size=30, chunk_overlap=10)

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    page_one = [chunk for chunk in chunks if chunk.page_number == 1]
    assert len(page_one) > 1
    assert page_one[0].source == "pricing.pdf p.1"
    assert page_one[1].text[:10] == page_one[0].text[-10:]
    assert any(chunk.page_number == 2 and "pricing" in chunk.text for chunk in chunks)


def test_plain_text_has_no_page_number() -> None:
    chunks = split_pages("notes.txt", [LoadedPage(page_number=None, text="Policy text")], 100, 20)

    assert len(chunks) == 1
    assert chunks[0].page_number is None
    assert chunks[0].source == "notes.txt"


def test_empty_text_produces_no_chunks() -> None:
    assert split_pages("empty.txt", [], 100, 20) == []
    assert split_pages("blank.txt", [LoadedPage(page_number=None, text="   \n")], 100, 20) == []
