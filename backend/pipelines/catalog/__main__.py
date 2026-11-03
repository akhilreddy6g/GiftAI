"""Command line for the catalog pipeline. Run from backend/:

    # every step, every category
    uv run python -m pipelines.catalog all
    # a quick try on one smaller category
    uv run python -m pipelines.catalog all --categories Musical_Instruments --scale 0.5
    # just one step
    uv run python -m pipelines.catalog load

``load`` writes to the database in DATABASE_URL (from the environment or backend/.env).
"""

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import httpx
import psycopg

from giftai.core.config import get_embedding_settings
from giftai.embeddings.dependencies import build_text_embedder
from pipelines.catalog import steps
from pipelines.catalog.config import CATEGORY_QUOTAS, SelectionRules
from pipelines.catalog.neighbors import AlsParameters
from pipelines.catalog.workspace import DEFAULT_WORKSPACE, Workspace

STEPS = ("download", "select", "embed", "neighbors", "load")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m pipelines.catalog", description=__doc__)
    parser.add_argument("step", choices=[*STEPS, "all"])
    parser.add_argument(
        "--categories",
        nargs="+",
        default=list(CATEGORY_QUOTAS),
        metavar="NAME",
        help="dataset categories, such as Home_and_Kitchen (default: all giftable ones)",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="multiply every category's product quota, such as 0.1 for a small trial",
    )
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--als-factors", type=int, default=AlsParameters.factors)
    parser.add_argument("--als-iterations", type=int, default=AlsParameters.iterations)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run(args)
    except (FileNotFoundError, RuntimeError, ValueError, httpx.HTTPError, psycopg.Error) as error:
        parser.exit(1, f"error: {error}\n")


def run(args: argparse.Namespace) -> None:
    workspace = Workspace(args.workspace)
    chosen = STEPS if args.step == "all" else (args.step,)

    if "download" in chosen:
        steps.download(workspace, args.categories)
    if "select" in chosen:
        steps.select(workspace, args.categories, SelectionRules(), args.scale)
    if "embed" in chosen:
        steps.embed(workspace, build_text_embedder(get_embedding_settings()))
    if "neighbors" in chosen:
        parameters = AlsParameters(factors=args.als_factors, iterations=args.als_iterations)
        steps.neighbors(workspace, args.categories, parameters)
    if "load" in chosen:
        steps.load(workspace)


if __name__ == "__main__":
    main()
