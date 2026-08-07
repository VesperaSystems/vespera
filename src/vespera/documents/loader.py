"""Document discovery and text extraction."""

from dataclasses import dataclass
from pathlib import Path

from vespera.documents import docx_, pdf

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


@dataclass
class Page:
    number: int | None  # 1-based page number, None when the format has no pages
    text: str


@dataclass
class Document:
    path: Path
    pages: list[Page]

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages)

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


def discover_documents(root: Path) -> list[Path]:
    """Recursively find supported documents under root, skipping hidden files/dirs."""
    found = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            found.append(path)
    return found


def load_document(path: Path) -> Document:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pages = pdf.extract_pages(path)
    elif suffix == ".docx":
        pages = [Page(number=None, text=docx_.extract_text(path))]
    else:  # .txt, .md
        pages = [Page(number=None, text=path.read_text(encoding="utf-8", errors="replace"))]
    return Document(path=path, pages=pages)
