"""Asks an LLM to draft candidate rules from each chapter.

Drafts are only candidates: nothing reaches the rulebook until a person approves it in
the review step. The model is told to write in its own words and never to quote, so the
rulebook holds our guidance and citations, not the sources' text.
"""

import hashlib
import json
import logging
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Annotated, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from giftai.gifting import Occasion, Relationship
from giftai.rulebook.models import RuleKind
from pipelines.rulebook.extraction import Chapter

logger = logging.getLogger(__name__)

# Google keeps this alias on its current Flash model; pass --model to pin one.
DEFAULT_MODEL = "gemini-flash-latest"
MAX_RULES_PER_CHAPTER = 8


class DraftedRule(BaseModel):
    """What the model returns for one rule."""

    rule: str = Field(description="One actionable sentence for choosing a gift, in your own words.")
    rationale: str = Field(description="One or two sentences on why it holds, in your own words.")
    kind: RuleKind = Field(description="'do' for advice to follow, 'dont' for a mistake to avoid.")
    relationships: list[Relationship] = Field(
        description="Who it applies to; empty if it applies to anyone."
    )
    occasions: list[Occasion] = Field(description="When it applies; empty if any occasion.")
    budget_min_usd: int | None = Field(description="Lowest gift price it applies to, if limited.")
    budget_max_usd: int | None = Field(description="Highest gift price it applies to, if limited.")


class DraftedRules(BaseModel):
    rules: list[DraftedRule]


class Candidate(BaseModel):
    """A drafted rule with where it came from, as the later steps read it."""

    model_config = ConfigDict(extra="forbid")

    id: str
    source_id: str
    location: str
    rule: Annotated[str, StringConstraints(strip_whitespace=True)]
    rationale: Annotated[str, StringConstraints(strip_whitespace=True)]
    kind: RuleKind
    relationships: list[Relationship]
    occasions: list[Occasion]
    budget_min_usd: int | None
    budget_max_usd: int | None


class RuleDrafter(Protocol):
    def draft(self, chapter: Chapter, source_title: str) -> list[DraftedRule]: ...


PROMPT = """\
You help build the rulebook of a gift recommender. Below is one section of "{title}".

Write up to {limit} rules a person could use when choosing a gift, each one supported by
this section. Rules must be practical and specific enough to change which gift gets
picked; skip anything about wrapping, etiquette of thank-you notes, history or anecdotes.
If the section has no such guidance, return an empty list.

Write every rule and rationale in your own words. Do not quote or closely paraphrase the
text. Keep each rule under 200 characters. Only limit relationships, occasions or budget
when the section clearly does.

Section: {location}
---
{text}
"""


class GeminiDrafter:
    """Drafts with the Gemini API, staying under the free tier's rate limits."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        requests_per_minute: float = 8,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        from google import genai  # The API's own dependency, only needed offline.

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._interval = 60.0 / requests_per_minute
        self._sleep = sleep
        self._last_request = 0.0

    def draft(self, chapter: Chapter, source_title: str) -> list[DraftedRule]:
        from google.genai import errors, types

        prompt = PROMPT.format(
            title=source_title,
            limit=MAX_RULES_PER_CHAPTER,
            location=chapter.location,
            text=chapter.text,
        )
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DraftedRules,
            temperature=0.2,
        )
        for attempt in range(6):
            self._wait_turn()
            try:
                response = self._client.models.generate_content(
                    model=self._model, contents=prompt, config=config
                )
            except errors.APIError as error:
                retryable = error.code == 429 or error.code >= 500
                if not retryable or attempt == 5:
                    raise RuntimeError(f"Gemini request failed: {error}") from error
                delay = min(30.0 * 2**attempt, 300.0)
                logger.warning("Gemini returned %s; retrying in %.0fs", error.code, delay)
                self._sleep(delay)
                continue
            parsed = response.parsed
            if isinstance(parsed, DraftedRules):
                return parsed.rules[:MAX_RULES_PER_CHAPTER]
            return DraftedRules.model_validate_json(response.text or '{"rules": []}').rules[
                :MAX_RULES_PER_CHAPTER
            ]
        raise AssertionError("unreachable")

    def _wait_turn(self) -> None:
        wait = self._last_request + self._interval - time.monotonic()
        if wait > 0:
            self._sleep(wait)
        self._last_request = time.monotonic()


def draft_candidates(
    chapters: Iterable[Chapter],
    titles: dict[str, str],
    drafter: RuleDrafter,
    candidates_file: Path,
) -> int:
    """Drafts every chapter not drafted yet, appending as it goes so that an interrupted
    run (or a rate limit) loses at most one chapter. Returns the chapters drafted now.
    """
    done = drafted_chapter_keys(candidates_file)
    candidates_file.parent.mkdir(parents=True, exist_ok=True)
    drafted = 0
    pending = [chapter for chapter in chapters if chapter.key not in done]
    for number, chapter in enumerate(pending, 1):
        rules = drafter.draft(chapter, titles[chapter.source_id])
        candidates = [_candidate(chapter, index, rule) for index, rule in enumerate(rules)]
        record = {
            "chapter": chapter.key,
            "candidates": [c.model_dump(mode="json") for c in candidates],
        }
        with candidates_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        drafted += 1
        logger.info(
            "Drafted %d rules from %s, %s (%d/%d)",
            len(candidates),
            chapter.source_id,
            chapter.location,
            number,
            len(pending),
        )
    return drafted


def drafted_chapter_keys(candidates_file: Path) -> set[str]:
    return {record["chapter"] for record in _records(candidates_file)}


def read_candidates(candidates_file: Path) -> list[Candidate]:
    return [
        Candidate.model_validate(candidate)
        for record in _records(candidates_file)
        for candidate in record["candidates"]
    ]


def _records(candidates_file: Path) -> list[dict[str, Any]]:
    if not candidates_file.exists():
        return []
    with candidates_file.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def _candidate(chapter: Chapter, index: int, rule: DraftedRule) -> Candidate:
    digest = hashlib.sha256(f"{chapter.key}|{index}".encode()).hexdigest()[:12]
    return Candidate(
        id=f"C-{digest}",
        source_id=chapter.source_id,
        location=chapter.location,
        **rule.model_dump(),
    )
