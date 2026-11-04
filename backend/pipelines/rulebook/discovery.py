"""Finds source files in the workspace and drafts their sources.yaml entries from each
file's own metadata, so a person only checks and corrects them.
"""

import logging
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from pypdf import PdfReader

from giftai.rulebook.models import SourceKind

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = frozenset({".pdf", ".epub", ".txt", ".md"})
# Papers rarely run past this many pages; books rarely stay under it.
_PAPER_MAX_PAGES = 60
_UNKNOWN_AUTHORS = "Unknown"
_YEAR = re.compile(r"(1[89]\d\d|20\d\d)")


@dataclass(frozen=True)
class DiscoveredSource:
    id: str
    title: str
    authors: str
    year: int | None
    kind: SourceKind
    # Relative to the workspace, with forward slashes.
    file: str


def discover_sources(
    root: Path, listed_files: set[Path], taken_ids: set[str]
) -> list[DiscoveredSource]:
    """Every supported file under ``root`` not listed yet, skipping the pipeline's own
    output folders.
    """
    listed = {path.resolve() for path in listed_files}
    taken = set(taken_ids)
    found: list[DiscoveredSource] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if (
            not path.is_file()
            or path.suffix.lower() not in SUPPORTED_SUFFIXES
            or relative.parts[0] == "chapters"
            or any(part.startswith(".") for part in relative.parts)
            or path.resolve() in listed
        ):
            continue
        title, authors, year, kind = _metadata(path)
        source_id = _unique(_slug(authors, title, year), taken)
        taken.add(source_id)
        found.append(DiscoveredSource(source_id, title, authors, year, kind, relative.as_posix()))
    return found


def render_entries(sources: list[DiscoveredSource]) -> str:
    """YAML list items for sources.yaml, flagging guesses that need a person's check."""
    lines: list[str] = []
    for source in sources:
        lines += [
            f"  - id: {source.id}",
            f"    title: {_quote(source.title)}",
            f"    authors: {_quote(source.authors)}"
            + ("   # TODO: fill in" if source.authors == _UNKNOWN_AUTHORS else ""),
            f"    year: {source.year if source.year is not None else 'null'}"
            + ("   # TODO: fill in" if source.year is None else ""),
            f"    kind: {source.kind.value}   # book, paper or article",
            f"    file: {_quote(source.file)}",
        ]
    return "\n".join(lines) + "\n"


def _metadata(path: Path) -> tuple[str, str, int | None, SourceKind]:
    title = authors = None
    year: int | None = None
    kind = SourceKind.BOOK
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            title, authors, year, pages = _pdf_metadata(path)
            if pages <= _PAPER_MAX_PAGES:
                kind = SourceKind.PAPER
        elif suffix == ".epub":
            title, authors, year = _epub_metadata(path)
    except Exception:  # Damaged metadata only costs us the guesses.
        logger.warning("Could not read the metadata of %s; guessing from its name", path)
    if year is None and (match := _YEAR.search(path.stem)):
        year = int(match.group(1))
    return (
        _clean(title) or _title_from_name(path.stem),
        _clean(authors) or _UNKNOWN_AUTHORS,
        year,
        kind,
    )


def _pdf_metadata(path: Path) -> tuple[str | None, str | None, int | None, int]:
    reader = PdfReader(path)
    info = reader.metadata
    year = None
    if info is not None and info.creation_date is not None:
        year = info.creation_date.year
    title = info.title if info is not None else None
    authors = info.author if info is not None else None
    return title, authors, year, len(reader.pages)


_DC = "{http://purl.org/dc/elements/1.1/}"
_CONTAINER_NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}


def _epub_metadata(path: Path) -> tuple[str | None, str | None, int | None]:
    # The XML parsed here comes from the developer's own book files.
    with zipfile.ZipFile(path) as book:
        container = ElementTree.fromstring(book.read("META-INF/container.xml"))  # noqa: S314
        rootfile = container.find(".//c:rootfile", _CONTAINER_NS)
        if rootfile is None:
            return None, None, None
        package = ElementTree.fromstring(  # noqa: S314
            book.read(str(PurePosixPath(rootfile.attrib["full-path"])))
        )
    title = package.findtext(f".//{_DC}title")
    creators = [element.text or "" for element in package.iter(f"{_DC}creator")]
    date = package.findtext(f".//{_DC}date") or ""
    match = _YEAR.search(date)
    return (
        title,
        ", ".join(c.strip() for c in creators if c.strip()),
        (int(match.group(1)) if match else None),
    )


def _clean(value: str | None) -> str:
    value = " ".join((value or "").split())
    # Tools often leave placeholders such as "Microsoft Word - draft3.docx".
    if not value or value.lower() in {"untitled", "unknown", "anonymous"} or ".doc" in value:
        return ""
    return value[:300]


def _title_from_name(stem: str) -> str:
    words = re.sub(r"[_\-.]+", " ", stem).strip()
    return words[:1].upper() + words[1:] if words else "Untitled"


def _slug(authors: str, title: str, year: int | None) -> str:
    def ascii_words(text: str) -> list[str]:
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
        return re.findall(r"[a-z0-9]+", text.lower())

    parts: list[str] = []
    if authors != _UNKNOWN_AUTHORS:
        # The first author's surname: "Galak, Jeff", "Jeff Galak" and
        # "Jeff Galak, Julian Givi" all give "galak".
        first = re.split(r";|&| and ", authors)[0]
        names = ascii_words(first.split(",")[0])
        if names:
            parts.append(names[0] if "," in first and len(names) == 1 else names[-1])
    parts += [word for word in ascii_words(title) if word not in {"a", "an", "the", "of"}][:4]
    if year is not None:
        parts.append(str(year))
    slug = "-".join(parts)[:60].strip("-")
    return slug or "source"


def _unique(slug: str, taken: set[str]) -> str:
    if slug not in taken:
        return slug
    number = 2
    while f"{slug[:56]}-{number}" in taken:
        number += 1
    return f"{slug[:56]}-{number}"


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
