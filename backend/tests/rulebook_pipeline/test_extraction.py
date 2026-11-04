"""Splitting source files into the sections the drafting model reads."""

import zipfile
from pathlib import Path

import pytest

from pipelines.rulebook import extraction
from pipelines.rulebook.extraction import extract_chapters, read_chapters, write_chapters

PARAGRAPH = "Gift givers often focus on the moment of opening, recipients on later use. " * 30


def test_markdown_is_split_by_headings(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text(f"Title page\n\n# Chapter one\n{PARAGRAPH}\n\n## Giving at work\n{PARAGRAPH}")

    chapters = extract_chapters("notes", path)

    # The title page is too short to be worth drafting from.
    assert [chapter.location for chapter in chapters] == ["Chapter one", "Giving at work"]
    assert all(chapter.source_id == "notes" for chapter in chapters)


def test_text_files_find_chapter_lines(tmp_path: Path) -> None:
    path = tmp_path / "book.txt"
    path.write_text(f"CHAPTER 1\n{PARAGRAPH}\nChapter II: Surprise\n{PARAGRAPH}")

    chapters = extract_chapters("book", path)

    assert [chapter.location for chapter in chapters] == ["CHAPTER 1", "Chapter II: Surprise"]


def test_long_chapters_are_cut_into_parts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extraction, "MAX_CHAPTER_CHARS", 5_000)
    path = tmp_path / "long.md"
    path.write_text("# Long\n" + "\n\n".join([PARAGRAPH] * 6))

    chapters = extract_chapters("long", path)

    assert [chapter.location for chapter in chapters] == [f"Long (part {n})" for n in (1, 2, 3)]
    assert all(len(chapter.text) <= 5_000 for chapter in chapters)


def test_repeated_headings_get_distinct_locations(tmp_path: Path) -> None:
    path = tmp_path / "repeats.md"
    path.write_text(f"# Summary\n{PARAGRAPH}\n# Summary\n{PARAGRAPH}")

    chapters = extract_chapters("repeats", path)

    assert [chapter.location for chapter in chapters] == ["Summary", "Summary (2)"]


def test_epub_follows_the_reading_order(tmp_path: Path) -> None:
    path = tmp_path / "book.epub"
    with zipfile.ZipFile(path, "w") as book:
        book.writestr(
            "META-INF/container.xml",
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
            '<rootfile full-path="OEBPS/content.opf"/></rootfiles></container>',
        )
        book.writestr(
            "OEBPS/content.opf",
            '<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
            '<item id="a" href="a.xhtml"/><item id="b" href="text/b.xhtml"/></manifest>'
            '<spine><itemref idref="b"/><itemref idref="a"/></spine></package>',
        )
        book.writestr(
            "OEBPS/a.xhtml",
            "<html><head><style>p {}</style></head>"
            f"<body><h1>Later</h1><p>{PARAGRAPH}</p></body></html>",
        )
        book.writestr(
            "OEBPS/text/b.xhtml",
            f"<html><body><h2>First <em>up</em></h2><p>{PARAGRAPH}</p></body></html>",
        )

    chapters = extract_chapters("book", path)

    assert [chapter.location for chapter in chapters] == ["First up", "Later"]
    assert "p {}" not in chapters[1].text


def test_unsupported_files_are_refused(tmp_path: Path) -> None:
    path = tmp_path / "book.mobi"
    path.write_bytes(b"")

    with pytest.raises(ValueError, match="unsupported"):
        extract_chapters("book", path)


def test_chapters_survive_writing_and_reading(tmp_path: Path) -> None:
    source = tmp_path / "notes.md"
    source.write_text(f"# One\n{PARAGRAPH}")
    chapters = extract_chapters("notes", source)

    write_chapters(tmp_path / "out" / "notes.jsonl", chapters)

    assert read_chapters(tmp_path / "out" / "notes.jsonl") == chapters


def test_long_text_without_paragraph_breaks_is_split_not_cut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(extraction, "MAX_CHAPTER_CHARS", 5_000)
    path = tmp_path / "pdf-like.md"
    # PDF text often has line breaks but no blank lines between paragraphs.
    body = "\n".join([PARAGRAPH[:900]] * 20)
    path.write_text("# Long\n" + body)

    chapters = extract_chapters("pdf-like", path)

    assert len(chapters) == 4
    assert all(len(chapter.text) <= 5_000 for chapter in chapters)
    assert sum(len(chapter.text) for chapter in chapters) >= len(body.strip()) - 20


def test_pdf_pages_before_the_first_bookmark_are_kept(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(8):
        writer.add_blank_page(width=612, height=792)
    # Like a paper that bookmarks only a table and an appendix.
    writer.add_outline_item("ucw067-TF1", 3)
    writer.add_outline_item("app1", 6)
    path = tmp_path / "paper.pdf"
    with path.open("wb") as file:
        writer.write(file)

    sections = extraction._pdf_sections(path)

    assert [location for location, _ in sections] == ["pp. 1-3", "ucw067-TF1", "app1"]
