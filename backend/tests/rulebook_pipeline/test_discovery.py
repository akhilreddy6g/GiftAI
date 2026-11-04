"""The scan step drafts sources.yaml entries from the files' own metadata."""

import zipfile
from pathlib import Path

from pypdf import PdfWriter

from giftai.rulebook.models import SourceKind
from pipelines.rulebook import steps
from pipelines.rulebook.sources import load_sources
from pipelines.rulebook.workspace import Workspace


def write_pdf(path: Path, pages: int, title: str | None = None, author: str | None = None) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    metadata = {"/CreationDate": "D:20160315000000"}
    if title:
        metadata["/Title"] = title
    if author:
        metadata["/Author"] = author
    writer.add_metadata(metadata)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        writer.write(file)


def write_epub(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as book:
        book.writestr(
            "META-INF/container.xml",
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
            '<rootfile full-path="content.opf"/></rootfiles></container>',
        )
        book.writestr(
            "content.opf",
            '<package xmlns="http://www.idpf.org/2007/opf" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><metadata>'
            "<dc:title>The Art of Giving</dc:title><dc:creator>Jane Doe</dc:creator>"
            "<dc:creator>John Roe</dc:creator><dc:date>2019-04-01</dc:date>"
            "</metadata></package>",
        )


def test_scan_lists_new_files_with_their_metadata(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)
    write_pdf(tmp_path / "papers" / "galak.pdf", 12, "Why Certain Gifts Are Great", "Galak, Jeff")
    write_pdf(tmp_path / "books" / "Big_Book-of_Gifts.pdf", 80)
    write_epub(tmp_path / "books" / "art.epub")
    (tmp_path / "notes.txt").write_text("my notes")
    (tmp_path / "chapters").mkdir()
    (tmp_path / "chapters" / "old.md").write_text("pipeline output, not a source")
    (tmp_path / "cover.jpg").write_bytes(b"")

    added = steps.scan(workspace)

    sources = {
        source.file.relative_to(tmp_path).as_posix(): source
        for source in load_sources(workspace.sources_file)
    }
    assert added == 4
    assert set(sources) == {
        "papers/galak.pdf",
        "books/Big_Book-of_Gifts.pdf",
        "books/art.epub",
        "notes.txt",
    }
    paper = sources["papers/galak.pdf"]
    assert (paper.id, paper.title, paper.authors, paper.year, paper.kind) == (
        "galak-why-certain-gifts-are-2016",
        "Why Certain Gifts Are Great",
        "Galak, Jeff",
        2016,
        SourceKind.PAPER,
    )
    book = sources["books/Big_Book-of_Gifts.pdf"]
    assert (book.title, book.authors, book.kind) == (
        "Big Book of Gifts",
        "Unknown",
        SourceKind.BOOK,
    )
    epub = sources["books/art.epub"]
    assert (epub.id, epub.authors, epub.year) == ("doe-art-giving-2019", "Jane Doe, John Roe", 2019)
    assert "# TODO: fill in" in workspace.sources_file.read_text()


def test_a_second_scan_only_adds_new_files_and_keeps_edits(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)
    write_epub(tmp_path / "art.epub")
    steps.scan(workspace)
    edited = workspace.sources_file.read_text().replace(
        "The Art of Giving", "The Art of Giving Well"
    )
    workspace.sources_file.write_text(edited + "# my own note\n")
    write_epub(tmp_path / "art-copy.epub")

    added = steps.scan(workspace)

    text = workspace.sources_file.read_text()
    ids = [source.id for source in load_sources(workspace.sources_file)]
    assert added == 1
    assert ids == ["doe-art-giving-2019", "doe-art-giving-2019-2"]
    assert "The Art of Giving Well" in text and "# my own note" in text
    assert steps.scan(workspace) == 0
