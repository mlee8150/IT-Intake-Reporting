"""Panel 7 (DEMAND & RISK: Stalled reviews) — active sub-tasks with no status
change in STALLED_THRESHOLD_DAYS+ days, by review team.

Sub-task level, per the "Reviews Needing Follow-up" reference sheet reviewed
with the report owner: a flat list of individual review sub-tasks, each with
its own status, its own last-status-updated date, and a Days-since-update
column — not a parent-request rollup. Uses each sub-task's most recent
transition-email timestamp as "last activity," which also resolves the risk
flagged in docs/OPEN_QUESTIONS.md of a parent's Jira `updated` field getting
bumped by bot/automation edits without a real reviewer acting.

Caveat (see docs/OPEN_QUESTIONS.md): `latest_transition_per_subtask` is only
as complete as the transition emails fetched for the current run's window —
a sub-task that has been stalled longer than that window, with zero activity
in it, won't appear here at all (invisible, not undercounted-but-present).
"""
from __future__ import annotations

from datetime import datetime

from ..models import TransitionEvent
from ..vocabulary import STALLED_THRESHOLD_DAYS


def compute_stalled(
    latest_transition_per_subtask: list[TransitionEvent],
    as_of: datetime,
    threshold_days: int = STALLED_THRESHOLD_DAYS,
) -> dict[str, int]:
    """`latest_transition_per_subtask` must contain exactly one event per open
    sub-task: the transition that put it into its *current* status (see
    pipeline._latest_transition_per_ticket — the same list panel 3 uses)."""
    counts: dict[str, int] = {}
    for event in latest_transition_per_subtask:
        if event.is_parent_request or event.review_team is None:
            continue
        days_since_update = (as_of - event.changed_at).days
        if days_since_update >= threshold_days:
            counts[event.review_team] = counts.get(event.review_team, 0) + 1
    return counts
