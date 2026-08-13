"""Panel 1 (TICKET FLOW: Backlog this week) — the opening -> closing balance
bridge for parent requests, built entirely from transition emails.

Per docs/DATA_SOURCES.md, the closing balance computed here MUST be
cross-checked against the Jira dashboard's live open-request count before the
deck is trusted — see `validate_against_jira`.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models import TransitionEvent

# Maps a transition's `to_status` to the balance-bridge bucket it belongs in.
# Adjust to match your real workflow's terminal/hold statuses — see
# docs/OPEN_QUESTIONS.md.
STATUS_TO_BUCKET = {
    "Completed": "completed",
    "Not Approved": "not_approved",
    "Cancelled": "cancelled",
    "On Hold": "on_hold",
}


@dataclass(frozen=True)
class BacklogResult:
    opening_balance: int
    newly_opened: int
    re_opened: int
    completed: int
    not_approved: int
    cancelled: int
    on_hold: int
    closing_balance: int

    def matches_jira(self, jira_active_count: int) -> bool:
        return self.closing_balance == jira_active_count


def compute_backlog(events: list[TransitionEvent], opening_balance: int) -> BacklogResult:
    """`events` should be this week's transition events for parent requests only."""
    parent_events = [e for e in events if e.is_parent_request]

    newly_opened = sum(1 for e in parent_events if e.from_status is None)
    re_opened = sum(
        1 for e in parent_events if e.to_status == "Re-opened" or e.from_status == "Completed"
    )
    bucket_counts = {bucket: 0 for bucket in set(STATUS_TO_BUCKET.values())}
    for e in parent_events:
        bucket = STATUS_TO_BUCKET.get(e.to_status)
        if bucket:
            bucket_counts[bucket] += 1

    closing_balance = (
        opening_balance
        + newly_opened
        + re_opened
        - bucket_counts.get("completed", 0)
        - bucket_counts.get("not_approved", 0)
        - bucket_counts.get("cancelled", 0)
        - bucket_counts.get("on_hold", 0)
    )

    return BacklogResult(
        opening_balance=opening_balance,
        newly_opened=newly_opened,
        re_opened=re_opened,
        completed=bucket_counts.get("completed", 0),
        not_approved=bucket_counts.get("not_approved", 0),
        cancelled=bucket_counts.get("cancelled", 0),
        on_hold=bucket_counts.get("on_hold", 0),
        closing_balance=closing_balance,
    )
