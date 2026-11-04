"""Splits each source file into chapters, the unit the drafting model reads at once.

PDFs are split by their outline (bookmarks) when they have one and by page ranges
otherwise; EPUBs by their reading order; text and Markdown by headings.
"""

import hashlib
import json
import logging
import re
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from pypdf import PdfReader
from pypdf.generic import Destination

logger = logging.getLogger(__name__)

# Shorter sections are front matter, copyright pages, indexes and the like.
MIN_CHAPTER_CHARS = 1_500
# Longer chapters are cut into parts, which keeps the drafting model focused.
MAX_CHAPTER_CHARS = 60_000
# PDFs without an outline are read this many pages at a time.
PAGES_PER_SECTION = 12


@dataclass(frozen=True)
class Chapter:
    source_id: str
    # How a rule cites it, such as "Chapter 3: Giving at work" or "pp. 13-24".
    location: str
    text: str

    @property
    def key(self) -> str:
        """Changes when the text does, so re-extracted sections are drafted again."""
        digest = hashlib.sha256(self.text.encode()).hexdigest()[:12]
        return f"{self.source_id}|{self.location}|{digest}"


def extract_chapters(source_id: str, path: Path) -> list[Chapter]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        sections = _pdf_sections(path)
    elif suffix == ".epub":
        sections = _epub_sections(path)
    elif suffix in {".txt", ".md"}:
        sections = _text_sections(path.read_text(encoding="utf-8", errors="replace"))
    else:
        raise ValueError(f"{path}: unsupported file type; use pdf, epub, txt or md")

    chapters: list[Chapter] = []
    for location, text in sections:
        text = _tidy(text)
        if len(text) < MIN_CHAPTER_CHARS:
            continue
        for part_location, part in _split_long(location, text):
            chapters.append(Chapter(source_id, part_location[:100], part))
    return _unique_locations(chapters)


def write_chapters(path: Path, chapters: Iterable[Chapter]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for chapter in chapters:
            file.write(json.dumps(asdict(chapter), ensure_ascii=False) + "\n")


def read_chapters(path: Path) -> list[Chapter]:
    with path.open(encoding="utf-8") as file:
        return [Chapter(**json.loads(line)) for line in file if line.strip()]


# PDF


def _pdf_sections(path: Path) -> list[tuple[str, str]]:
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    starts = _outline_starts(reader)
    if len(starts) < 2:
        return [
            (
                f"pp. {first + 1}-{min(first + PAGES_PER_SECTION, len(pages))}",
                "\n".join(pages[first : first + PAGES_PER_SECTION]),
            )
            for first in range(0, len(pages), PAGES_PER_SECTION)
        ]
    sections: list[tuple[str, str]] = []
    if starts[0][1] > 0:
        # Papers often bookmark only figures or appendices; keep what comes before.
        opening = starts[0][1]
        sections.append((f"pp. 1-{opening}", "\n".join(pages[:opening])))
    for index, (title, first) in enumerate(starts):
        end = starts[index + 1][1] if index + 1 < len(starts) else len(pages)
        sections.append((title, "\n".join(pages[first:end])))
    return sections


def _outline_starts(reader: PdfReader) -> list[tuple[str, int]]:
    """Top-level bookmarks as (title, first page), in page order."""
    try:
        outline = reader.outline
    except Exception:  # A damaged outline only costs us the chapter titles.
        logger.warning("Could not read the outline; splitting by pages instead")
        return []
    starts: dict[int, str] = {}
    for item in outline:
        if isinstance(item, Destination):
            try:
                page = reader.get_destination_page_number(item)
            except Exception:  # A bookmark pointing nowhere; the others still work.
                logger.debug("Skipping a broken bookmark", exc_info=True)
                continue
            title = str(item.title or "").strip()
            if page is not None and page >= 0 and title:
                starts.setdefault(page, title)
    return [(title, page) for page, title in sorted(starts.items())]


# EPUB

_CONTAINER_NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
_OPF_NS = {"opf": "http://www.idpf.org/2007/opf"}


def _epub_sections(path: Path) -> list[tuple[str, str]]:
    # The XML parsed here comes from the developer's own book files.
    with zipfile.ZipFile(path) as book:
        container = ElementTree.fromstring(book.read("META-INF/container.xml"))  # noqa: S314
        rootfile = container.find(".//c:rootfile", _CONTAINER_NS)
        if rootfile is None:
            raise ValueError(f"{path}: not a valid EPUB (no rootfile)")
        opf_path = PurePosixPath(rootfile.attrib["full-path"])
        package = ElementTree.fromstring(book.read(str(opf_path)))  # noqa: S314
        manifest = {
            item.attrib["id"]: item.attrib["href"]
            for item in package.iterfind(".//opf:manifest/opf:item", _OPF_NS)
        }
        sections: list[tuple[str, str]] = []
        for number, itemref in enumerate(package.iterfind(".//opf:spine/opf:itemref", _OPF_NS), 1):
            href = manifest.get(itemref.attrib.get("idref", ""))
            if href is None:
                continue
            member = str(opf_path.parent / href.split("#", 1)[0])
            parser = _HtmlText()
            parser.feed(book.read(member).decode("utf-8", errors="replace"))
            sections.append((parser.heading or f"Section {number}", parser.text()))
    return sections


class _HtmlText(HTMLParser):
    _BLOCKS = frozenset({"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "blockquote"})
    _SKIPPED = frozenset({"script", "style", "head"})

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skipping = 0
        self._in_heading = False
        self._heading: list[str] = []
        self.heading: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIPPED:
            self._skipping += 1
        elif tag in {"h1", "h2"} and self.heading is None:
            self._in_heading = True
        if tag in self._BLOCKS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIPPED:
            self._skipping = max(0, self._skipping - 1)
        elif tag in {"h1", "h2"} and self._in_heading:
            self._in_heading = False
            self.heading = " ".join("".join(self._heading).split()) or None
        if tag in self._BLOCKS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skipping:
            return
        self._parts.append(data)
        if self._in_heading:
            self._heading.append(data)

    def text(self) -> str:
        return "".join(self._parts)


# Plain text and Markdown

_HEADING = re.compile(r"^(?:#{1,2}\s+.+|(?:chapter|part)\s+[\divxlc]+\b.*)$", re.IGNORECASE)


def _text_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    title = "Introduction"
    lines: list[str] = []
    for line in text.splitlines():
        if _HEADING.match(line.strip()):
            sections.append((title, "\n".join(lines)))
            title, lines = line.strip().lstrip("#").strip(), []
        else:
            lines.append(line)
    sections.append((title, "\n".join(lines)))
    return sections


# Shared


def _tidy(text: str) -> str:
    text = re.sub(r"-\n(?=[a-z])", "", text)  # Words hyphenated across lines.
    text = re.sub("[ \t\u00a0]+", " ", text)
    return re.sub(r"\n\s*\n\s*", "\n\n", text).strip()


def _split_long(location: str, text: str) -> Iterator[tuple[str, str]]:
    if len(text) <= MAX_CHAPTER_CHARS:
        yield location, text
        return
    parts: list[str] = []
    current = ""
    for piece in _pieces(text):
        if current and len(current) + len(piece) + 1 > MAX_CHAPTER_CHARS:
            parts.append(current)
            current = ""
        current = f"{current}\n{piece}" if current else piece
    parts.append(current)
    for number, part in enumerate(parts, 1):
        yield f"{location} (part {number})", part


def _pieces(text: str) -> Iterator[str]:
    """Paragraphs, or lines when PDF text has no paragraph breaks, or fixed-size cuts of a
    line longer still, each at most MAX_CHAPTER_CHARS long.
    """
    for paragraph in text.split("\n\n"):
        if len(paragraph) <= MAX_CHAPTER_CHARS:
            yield paragraph
            continue
        for line in paragraph.split("\n"):
            for start in range(0, len(line), MAX_CHAPTER_CHARS):
                yield line[start : start + MAX_CHAPTER_CHARS]


def _unique_locations(chapters: list[Chapter]) -> list[Chapter]:
    seen: dict[str, int] = {}
    unique: list[Chapter] = []
    for chapter in chapters:
        count = seen.get(chapter.location, 0) + 1
        seen[chapter.location] = count
        location = chapter.location if count == 1 else f"{chapter.location[:94]} ({count})"
        unique.append(Chapter(chapter.source_id, location, chapter.text))
    return unique
