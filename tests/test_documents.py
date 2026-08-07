from pathlib import Path

from vespera.documents.loader import discover_documents, load_document


def test_discover_finds_supported_files_recursively(tmp_path: Path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.pdf").write_bytes(b"")
    (tmp_path / "sub" / "b.docx").write_bytes(b"")
    (tmp_path / "sub" / "c.txt").write_text("hello")
    (tmp_path / "d.md").write_text("# hi")
    (tmp_path / "ignore.xlsx").write_bytes(b"")
    (tmp_path / ".hidden.txt").write_text("secret")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "e.txt").write_text("internal")

    found = [p.name for p in discover_documents(tmp_path)]
    assert found == ["a.pdf", "d.md", "b.docx", "c.txt"]


def test_load_pdf_extracts_pages(sample_pdf: Path):
    document = load_document(sample_pdf)
    assert len(document.pages) == 2
    assert document.pages[0].number == 1
    assert "terminated for convenience" in document.pages[0].text
    assert "England and Wales" in document.pages[1].text
    assert not document.is_empty


def test_load_txt(tmp_path: Path):
    path = tmp_path / "note.txt"
    path.write_text("Termination on 30 days notice.")
    document = load_document(path)
    assert document.pages[0].number is None
    assert "30 days" in document.text
