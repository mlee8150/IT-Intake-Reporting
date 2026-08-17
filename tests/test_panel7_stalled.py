"""Panel 7 is sub-task level (see panel7_stalled.py's docstring): stalled
counts come from each sub-task's own latest transition, not the parent
request's Jira `updated` field.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from it_intake_reporting.models import TransitionEvent
from it_intake_reporting.panels.panel7_stalled import compute_stalled

AS_OF = datetime(2026, 8, 17, tzinfo=timezone.utc)


def _event(ticket_key, review_team, days_ago, is_parent_request=False) -> TransitionEvent:
    return TransitionEvent(
        ticket_key=ticket_key,
        is_parent_request=is_parent_request,
        review_team=review_team,
        from_status="Open",
        to_status="Review In Progress",
        changed_at=AS_OF - timedelta(days=days_ago),
        changed_by="Someone",
        raw_subject=f"{ticket_key} moved",
    )


def test_counts_subtasks_at_or_past_threshold_by_team():
    events = [
        _event("TI-1", "Legal", days_ago=10),  # stalled
        _event("TI-2", "Legal", days_ago=7),  # exactly at threshold — stalled
        _event("TI-3", "IAM", days_ago=3),  # not stalled
        _event("TI-4", "CyberArch", days_ago=8),  # stalled
    ]

    result = compute_stalled(events, as_of=AS_OF)

    assert result == {"Legal": 2, "CyberArch": 1}


def test_ignores_parent_requests_and_unassigned_team():
    events = [
        _event("TI-5", review_team=None, days_ago=30),
        _event("TI-6", review_team="Legal", days_ago=30, is_parent_request=True),
    ]

    result = compute_stalled(events, as_of=AS_OF)

    assert result == {}


def test_respects_custom_threshold():
    events = [_event("TI-7", "TPRM", days_ago=4)]

    assert compute_stalled(events, as_of=AS_OF, threshold_days=7) == {}
    assert compute_stalled(events, as_of=AS_OF, threshold_days=3) == {"TPRM": 1}
