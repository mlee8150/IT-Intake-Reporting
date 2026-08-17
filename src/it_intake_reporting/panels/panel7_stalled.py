"""Panel 7 (DEMAND & RISK: Stalled reviews) — open review sub-tasks by team.

Sub-task level, per the "Reviews Needing Follow-up" reference sheet reviewed
with the report owner: a flat list of individual review sub-tasks, each with
its own status and last-status-updated date. No day-count threshold is
applied here — per the report owner, the count is whatever the data itself
shows (every open sub-task currently tracked), not a cutoff we impose.

Uses each sub-task's most recent transition-email timestamp to identify it
as currently open, which also avoids the risk (flagged in
docs/OPEN_QUESTIONS.md) of a parent's Jira `updated` field getting bumped by
bot/automation edits without a real reviewer acting.

Caveat (see docs/OPEN_QUESTIONS.md): `latest_transition_per_subtask` is only
as complete as the transition emails fetched for the current run's window —
a sub-task with zero activity in that window won't appear here at all.
"""
from __future__ import annotations

from ..models import TransitionEvent


def compute_stalled(latest_transition_per_subtask: list[TransitionEvent]) -> dict[str, int]:
    """`latest_transition_per_subtask` must contain exactly one event per open
    sub-task: the transition that put it into its *current* status (see
    pipeline._latest_transition_per_ticket — the same list panel 3 uses)."""
    counts: dict[str, int] = {}
    for event in latest_transition_per_subtask:
        if event.is_parent_request or event.review_team is None:
            continue
        counts[event.review_team] = counts.get(event.review_team, 0) + 1
    return counts
