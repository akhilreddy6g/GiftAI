"""Groups candidates that say the same thing, so a person reviews each idea once and the
approved rule can cite every source that backs it.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from giftai.embeddings.base import TextEmbedder
from pipelines.rulebook.drafting import Candidate

# Cosine similarity above which two drafts count as the same rule. bge-small puts
# paraphrases at about 0.85-0.95 and merely related advice at about 0.7-0.8.
DEFAULT_THRESHOLD = 0.86


@dataclass(frozen=True)
class CandidateGroup:
    candidate_ids: tuple[str, ...]


def group_candidates(
    candidates: list[Candidate], embedder: TextEmbedder, threshold: float = DEFAULT_THRESHOLD
) -> list[CandidateGroup]:
    """Greedy grouping: each draft joins the first group whose first member it matches,
    in kind as well as meaning ("do X" and "don't X" read alike but never merge).
    """
    if not candidates:
        return []
    vectors = embedder.embed_documents([candidate.rule for candidate in candidates])
    leaders: list[int] = []
    members: list[list[int]] = []
    for index, candidate in enumerate(candidates):
        best, best_score = -1, threshold
        for group, leader in enumerate(leaders):
            if candidates[leader].kind != candidate.kind:
                continue
            score = float(np.dot(vectors[index], vectors[leader]))
            if score >= best_score:
                best, best_score = group, score
        if best < 0:
            leaders.append(index)
            members.append([index])
        else:
            members[best].append(index)
    # Ideas several sources agree on come first: they are the rulebook's backbone.
    members.sort(key=lambda group: (-len({candidates[i].source_id for i in group}), group[0]))
    return [CandidateGroup(tuple(candidates[i].id for i in group)) for group in members]


def write_groups(path: Path, groups: list[CandidateGroup]) -> None:
    path.write_text(json.dumps([list(group.candidate_ids) for group in groups], indent=1))


def read_groups(path: Path) -> list[CandidateGroup]:
    return [CandidateGroup(tuple(ids)) for ids in json.loads(path.read_text())]
