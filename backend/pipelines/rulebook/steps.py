"""Each step of the rulebook pipeline, wired to its files."""

import logging
from pathlib import Path

from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from giftai.core.config import DatabaseSettings, get_database_settings
from giftai.embeddings.base import TextEmbedder
from pipelines.rulebook.discovery import discover_sources, render_entries
from pipelines.rulebook.document import RULEBOOK_FILE, load_rulebook
from pipelines.rulebook.drafting import RuleDrafter, draft_candidates, read_candidates
from pipelines.rulebook.extraction import extract_chapters, read_chapters, write_chapters
from pipelines.rulebook.grouping import DEFAULT_THRESHOLD, group_candidates, write_groups
from pipelines.rulebook.seeding import SeedReport, seed_rulebook
from pipelines.rulebook.sources import SOURCES_HEADER, LocalSource, load_sources
from pipelines.rulebook.workspace import Workspace

logger = logging.getLogger(__name__)


def sources(workspace: Workspace, only: list[str] | None = None) -> list[LocalSource]:
    listed = load_sources(workspace.sources_file)
    if not only:
        return listed
    unknown = set(only) - {source.id for source in listed}
    if unknown:
        raise ValueError(f"Not in {workspace.sources_file}: {', '.join(sorted(unknown))}")
    return [source for source in listed if source.id in only]


def scan(workspace: Workspace) -> int:
    """Adds an entry to sources.yaml for every new file in the workspace, guessed from
    the file's metadata. Returns how many were added.
    """
    workspace.root.mkdir(parents=True, exist_ok=True)
    path = workspace.sources_file
    listed = load_sources(path) if path.exists() else []
    found = discover_sources(
        workspace.root, {source.file for source in listed}, {source.id for source in listed}
    )
    if not found:
        logger.info("No new pdf, epub, txt or md files in %s", workspace.root)
        return 0
    entries = render_entries(found)
    if listed:
        existing = path.read_text(encoding="utf-8")
        path.write_text(existing.rstrip("\n") + "\n" + entries, encoding="utf-8")
    else:
        path.write_text(SOURCES_HEADER + "sources:\n" + entries, encoding="utf-8")
    load_sources(path)  # What was written must read back.
    for source in found:
        logger.info("Added %s (%s): %s", source.id, source.file, source.title)
    logger.info("Check the titles, authors, years and kinds in %s before extracting", path)
    return len(found)


def extract(workspace: Workspace, chosen: list[LocalSource]) -> None:
    for source in chosen:
        if not source.file.exists():
            raise FileNotFoundError(f"{source.id}: {source.file} does not exist")
        chapters = extract_chapters(source.id, source.file)
        if not chapters:
            raise ValueError(f"{source.id}: no text found (a scanned PDF needs OCR first)")
        write_chapters(workspace.chapters_file(source.id), chapters)
        characters = sum(len(chapter.text) for chapter in chapters)
        logger.info("%s: %d sections, %d characters", source.id, len(chapters), characters)


def draft(workspace: Workspace, chosen: list[LocalSource], drafter: RuleDrafter) -> None:
    chapters = [
        chapter
        for source in chosen
        for chapter in read_chapters(
            workspace.require(workspace.chapters_file(source.id), "extract")
        )
    ]
    titles = {source.id: source.title for source in chosen}
    drafted = draft_candidates(chapters, titles, drafter, workspace.candidates_file)
    logger.info("Drafted %d new sections; %d were already done", drafted, len(chapters) - drafted)


def group(
    workspace: Workspace, embedder: TextEmbedder, threshold: float = DEFAULT_THRESHOLD
) -> None:
    candidates = read_candidates(workspace.require(workspace.candidates_file, "draft"))
    groups = group_candidates(candidates, embedder, threshold)
    write_groups(workspace.groups_file, groups)
    logger.info("Grouped %d drafts into %d ideas", len(candidates), len(groups))


def seed(rulebook_file: Path = RULEBOOK_FILE, database_url: str | None = None) -> SeedReport:
    rulebook = load_rulebook(rulebook_file)
    if database_url is not None:
        settings = DatabaseSettings(database_url=SecretStr(database_url))
    else:
        try:
            settings = get_database_settings()
        except ValidationError as error:
            raise RuntimeError("Set DATABASE_URL to the database to seed.") from error
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with Session(engine) as session:
            report = seed_rulebook(session, rulebook)
    finally:
        engine.dispose()
    logger.info(
        "Seeded %d sources and %d active rules; retired %d",
        report.sources,
        report.active_rules,
        report.retired_rules,
    )
    return report
