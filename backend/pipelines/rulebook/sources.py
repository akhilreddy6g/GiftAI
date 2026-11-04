"""The developer's list of sources: what each one is and where its file sits locally."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from pipelines.rulebook.document import SourceEntry

EXAMPLE = """\
sources:
  - id: galak-givi-williams-2016          # lowercase slug, cited by rules
    title: Why Certain Gifts Are Great to Give but Not to Get
    authors: Jeff Galak, Julian Givi, Elanor F. Williams
    year: 2016
    kind: paper                           # book, paper or article
    file: papers/galak-givi-williams-2016.pdf   # relative to this folder; pdf, epub, txt or md
"""


class LocalSource(SourceEntry):
    model_config = ConfigDict(extra="forbid")

    file: Path


class SourceList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[LocalSource]


def load_sources(path: Path) -> list[LocalSource]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. Create it to list your books and papers, like this:\n\n{EXAMPLE}"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = SourceList.model_validate(data).sources
    ids = [source.id for source in sources]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ValueError(f"{path}: duplicate source ids: {', '.join(duplicates)}")
    for source in sources:
        if not source.file.is_absolute():
            source.file = path.parent / source.file
    return sources
