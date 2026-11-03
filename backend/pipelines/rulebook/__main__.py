"""Command line for the rulebook pipeline. Run from backend/:

    uv run python -m pipelines.rulebook extract   # sources.yaml files -> sections
    uv run python -m pipelines.rulebook draft     # sections -> drafted rules (needs GEMINI_API_KEY)
    uv run python -m pipelines.rulebook group     # similar drafts -> one idea each
    uv run python -m pipelines.rulebook review    # you approve, edit or reject each idea
    uv run python -m pipelines.rulebook seed      # rulebook.yaml -> the database

Books and everything drawn from their text stay in backend/data/rulebook, which git
ignores. Only rulebook/rulebook.yaml, our own rules and their citations, is committed.
"""

import argparse
import logging
import os
import shlex
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy.exc
import yaml
from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from giftai.core.config import get_embedding_settings
from giftai.embeddings.dependencies import build_text_embedder
from pipelines.rulebook import steps
from pipelines.rulebook.document import RULEBOOK_FILE
from pipelines.rulebook.drafting import DEFAULT_MODEL, Candidate, GeminiDrafter, read_candidates
from pipelines.rulebook.grouping import DEFAULT_THRESHOLD, read_groups
from pipelines.rulebook.review import Review, run_review
from pipelines.rulebook.workspace import DEFAULT_WORKSPACE, Workspace

STEPS = ("extract", "draft", "group", "review", "seed")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m pipelines.rulebook",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("step", choices=STEPS)
    parser.add_argument("--sources", nargs="+", metavar="ID", help="only these source ids")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--rulebook", type=Path, default=RULEBOOK_FILE)
    parser.add_argument("--model", default=None, help=f"Gemini model (default: {DEFAULT_MODEL})")
    parser.add_argument("--requests-per-minute", type=float, default=8)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "huggingface_hub", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        run(args)
    except (
        FileNotFoundError,
        RuntimeError,
        ValueError,
        ValidationError,
        sqlalchemy.exc.SQLAlchemyError,
    ) as error:
        parser.exit(1, f"error: {error}\n")
    except KeyboardInterrupt:
        parser.exit(130, "\nstopped; progress so far is saved\n")


def run(args: argparse.Namespace) -> None:
    workspace = Workspace(args.workspace)
    if args.step == "seed":
        steps.seed(args.rulebook)
        return
    chosen = steps.sources(workspace, args.sources)
    if args.step == "extract":
        steps.extract(workspace, chosen)
    elif args.step == "draft":
        steps.draft(workspace, chosen, _gemini(args))
    elif args.step == "group":
        steps.group(workspace, build_text_embedder(get_embedding_settings()), args.threshold)
    elif args.step == "review":
        review = Review(
            read_candidates(workspace.require(workspace.candidates_file, "draft")),
            read_groups(workspace.require(workspace.groups_file, "group")),
            chosen,
            args.rulebook,
            workspace.review_file,
        )
        run_review(review, edit=_edit_in_editor)


class DraftingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: SecretStr | None = None
    gemini_model: str = DEFAULT_MODEL


def _gemini(args: argparse.Namespace) -> GeminiDrafter:
    settings = DraftingSettings()
    if settings.gemini_api_key is None:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Create a free key at aistudio.google.com/apikey "
            "and put it in backend/.env."
        )
    model = args.model or settings.gemini_model
    return GeminiDrafter(
        settings.gemini_api_key.get_secret_value(), model, args.requests_per_minute
    )


_EDITABLE = (
    "rule",
    "rationale",
    "kind",
    "relationships",
    "occasions",
    "budget_min_usd",
    "budget_max_usd",
)


def _edit_in_editor(draft: Candidate) -> Candidate | None:
    """Opens the draft in $EDITOR as YAML; returns the edited draft, or None if unchanged."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    original = yaml.safe_dump(
        draft.model_dump(mode="json", include=set(_EDITABLE)), sort_keys=False, width=100
    )
    with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=False, encoding="utf-8") as file:
        file.write(original)
        path = Path(file.name)
    try:
        # The developer's own editor, on a file this process just wrote.
        subprocess.run([*shlex.split(editor), str(path)], check=True)  # noqa: S603
        edited = path.read_text(encoding="utf-8")
    finally:
        path.unlink(missing_ok=True)
    if edited == original:
        return None
    fields = yaml.safe_load(edited)
    if not isinstance(fields, dict):
        raise ValueError("the edited draft must be a YAML mapping")
    unknown = set(fields) - set(_EDITABLE)
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
    return Candidate.model_validate({**draft.model_dump(), **fields})


if __name__ == "__main__":
    main()
