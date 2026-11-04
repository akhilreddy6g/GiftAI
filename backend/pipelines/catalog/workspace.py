"""Where each pipeline step reads and writes its files."""

from dataclasses import dataclass
from pathlib import Path

# backend/data/catalog, which git ignores: dataset files never enter the repo.
DEFAULT_WORKSPACE = Path(__file__).resolve().parents[2] / "data" / "catalog"


@dataclass(frozen=True)
class Workspace:
    root: Path = DEFAULT_WORKSPACE

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    def meta_file(self, category: str) -> Path:
        return self.raw_dir / f"meta_{category}.jsonl.gz"

    def ratings_file(self, category: str) -> Path:
        return self.raw_dir / f"ratings_{category}.csv.gz"

    @property
    def products_file(self) -> Path:
        return self.root / "products.jsonl"

    @property
    def embeddings_file(self) -> Path:
        return self.root / "embeddings.npz"

    @property
    def neighbors_file(self) -> Path:
        return self.root / "neighbors.npz"

    @property
    def neighbors_report_file(self) -> Path:
        return self.root / "neighbors_report.json"

    def require(self, path: Path, produced_by: str) -> Path:
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing; run the '{produced_by}' step first.")
        return path
