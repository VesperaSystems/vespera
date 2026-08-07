"""PDF text extraction via PyMuPDF."""

from pathlib import Path

import pymupdf


def extract_pages(path: Path) -> list:
    from vespera.documents.loader import Page

    pages = []
    with pymupdf.open(path) as doc:
        for index, page in enumerate(doc, start=1):
            pages.append(Page(number=index, text=page.get_text()))
    return pages
