"""Panel 7 is sub-task level (see panel7_stalled.py's docstring): it counts
every currently-tracked open review sub-task by team, from each sub-task's
latest transition — no day-count threshold, per the report owner.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from it_intake_reporting.models import TransitionEvent
from it_intake_reporting.panels.panel7_stalled import compute_stalled

CHANGED_AT = datetime(2026, 8, 10, tzinfo=timezone.utc)


def _event(ticket_key, review_team, is_parent_request=False) -> TransitionEvent:
    return TransitionEvent(
        ticket_key=ticket_key,
        is_parent_request=is_parent_request,
        review_team=review_team,
        from_status="Open",
        to_status="Review In Progress",
        changed_at=CHANGED_AT,
        changed_by="Someone",
        raw_subject=f"{ticket_key} moved",
    )


def test_counts_open_subtasks_by_team():
    events = [
        _event("TI-1", "Legal"),
        _event("TI-2", "Legal"),
        _event("TI-3", "IAM"),
        _event("TI-4", "CyberArch"),
    ]

    result = compute_stalled(events)

    assert result == {"Legal": 2, "IAM": 1, "CyberArch": 1}


def test_ignores_parent_requests_and_unassigned_team():
    events = [
        _event("TI-5", review_team=None),
        _event("TI-6", review_team="Legal", is_parent_request=True),
    ]

    result = compute_stalled(events)

    assert result == {}
