"""Panel 7 (DEMAND & RISK: Stalled reviews) — active requests with no update
in STALLED_THRESHOLD_DAYS+ days, by review team.

Uses Jira's `updated` timestamp as the "last activity" signal. If your
workflow has bot/automation edits that bump `updated` without real reviewer
activity, this will undercount stalled tickets — see docs/OPEN_QUESTIONS.md.
"""
from __future__ import annotations

from datetime import datetime

from ..models import JiraRequest
from ..vocabulary import STALLED_THRESHOLD_DAYS


def compute_stalled(
    requests: list[JiraRequest], as_of: datetime, threshold_days: int = STALLED_THRESHOLD_DAYS
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for request in requests:
        days_since_update = (as_of - request.updated).days
        if days_since_update >= threshold_days:
            team = request.review_team or "Unassigned"
            counts[team] = counts.get(team, 0) + 1
    return counts
