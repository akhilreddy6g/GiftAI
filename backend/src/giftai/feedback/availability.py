"""Turns found / not-found votes into a product's availability, and that into a ranking
weight. There is no free, terms-compliant way to check Amazon live, so users tell us.
"""

from dataclasses import dataclass
from enum import StrEnum


class AvailabilityStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    LIKELY_GONE = "likely_gone"


# Likely-gone products sink rather than disappear: the votes may be wrong, or the listing
# may come back, and the search-link fallback still leads somewhere useful.
RANKING_WEIGHT = {
    AvailabilityStatus.VERIFIED: 1.0,
    AvailabilityStatus.UNVERIFIED: 1.0,
    AvailabilityStatus.LIKELY_GONE: 0.25,
}


@dataclass(frozen=True)
class VoteCounts:
    found: int = 0
    not_found: int = 0

    @property
    def status(self) -> AvailabilityStatus:
        """The majority decides; no votes or a tie leaves the product unverified."""
        if self.found > self.not_found:
            return AvailabilityStatus.VERIFIED
        if self.not_found > self.found:
            return AvailabilityStatus.LIKELY_GONE
        return AvailabilityStatus.UNVERIFIED
