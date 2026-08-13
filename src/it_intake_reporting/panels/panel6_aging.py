"""Panel 6 (DEMAND & RISK: Aging requests) — active parent requests bucketed
by age since creation, by review team.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..models import JiraRequest
from ..vocabulary import AGING_BUCKETS


def _bucket_label(days_open: int) -> str:
    for low, high in AGING_BUCKETS:
        if high is None:
            if days_open >= low:
                return f"> {low - 1} days"
        elif low <= days_open <= high:
            return f"{low}–{high} days"
    raise AssertionError(f"No bucket matched {days_open} days — check AGING_BUCKETS")


@dataclass(frozen=True)
class AgingResult:
    by_team_and_bucket: dict[str, dict[str, int]]
    total_by_bucket: dict[str, int] = field(default_factory=dict)

    @property
    def total_over_90_days(self) -> int:
        over_90_label = _bucket_label(9999)
        return self.total_by_bucket.get(over_90_label, 0)


def compute_aging(requests: list[JiraRequest], as_of: datetime) -> AgingResult:
    by_team: dict[str, dict[str, int]] = {}
    totals: dict[str, int] = {}
    for request in requests:
        days_open = (as_of - request.created).days
        bucket = _bucket_label(days_open)
        team = request.review_team or "Unassigned"
        by_team.setdefault(team, {}).setdefault(bucket, 0)
        by_team[team][bucket] += 1
        totals[bucket] = totals.get(bucket, 0) + 1
    return AgingResult(by_team_and_bucket=by_team, total_by_bucket=totals)
