"""Where the rulebook pipeline keeps its working files."""

from dataclasses import dataclass
from pathlib import Path

# backend/data/rulebook, which git ignores: the books and anything drawn from their text
# stay on the developer's machine.
DEFAULT_WORKSPACE = Path(__file__).resolve().parents[2] / "data" / "rulebook"


@dataclass(frozen=True)
class Workspace:
    root: Path = DEFAULT_WORKSPACE

    @property
    def sources_file(self) -> Path:
        """The developer's list of sources and where each file is."""
        return self.root / "sources.yaml"

    @property
    def chapters_dir(self) -> Path:
        return self.root / "chapters"

    def chapters_file(self, source_id: str) -> Path:
        return self.chapters_dir / f"{source_id}.jsonl"

    @property
    def candidates_file(self) -> Path:
        return self.root / "candidates.jsonl"

    @property
    def groups_file(self) -> Path:
        return self.root / "groups.json"

    @property
    def review_file(self) -> Path:
        return self.root / "review.json"

    def require(self, path: Path, produced_by: str) -> Path:
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing; run the '{produced_by}' step first.")
        return path
