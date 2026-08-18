"""SubtaskTransitionStore: persists "latest known transition per sub-task"
across runs, so a sub-task with zero activity in one run's mailbox fetch
window doesn't just vanish from panels 3 and 7 (see the module docstring).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from it_intake_reporting.history.subtask_transition_store import SubtaskTransitionStore
from it_intake_reporting.models import TransitionEvent

BASE = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def _event(ticket_key, to_status, changed_at, review_team="Legal") -> TransitionEvent:
    return TransitionEvent(
        ticket_key=ticket_key,
        is_parent_request=False,
        review_team=review_team,
        from_status="Open",
        to_status=to_status,
        changed_at=changed_at,
        changed_by="Someone",
        raw_subject=f"{ticket_key} moved",
    )


def test_round_trips_a_tz_aware_datetime(tmp_path):
    store = SubtaskTransitionStore(tmp_path / "store.xlsx")
    store.merge_and_save([_event("TI-1", "Review In Progress", BASE)])

    reloaded = store.read_all()

    assert len(reloaded) == 1
    assert reloaded[0].changed_at == BASE
    assert reloaded[0].changed_at.tzinfo is not None


def test_second_run_keeps_tickets_untouched_this_run(tmp_path):
    store = SubtaskTransitionStore(tmp_path / "store.xlsx")
    store.merge_and_save([_event("TI-1", "Review In Progress", BASE)])

    # Second run: TI-1 didn't appear in this run's mailbox fetch at all.
    merged = store.merge_and_save([_event("TI-2", "Open", BASE + timedelta(days=7))])

    keys = {e.ticket_key for e in merged}
    assert keys == {"TI-1", "TI-2"}


def test_newer_transition_overwrites_older_for_same_ticket(tmp_path):
    store = SubtaskTransitionStore(tmp_path / "store.xlsx")
    store.merge_and_save([_event("TI-1", "Open", BASE)])
    merged = store.merge_and_save([_event("TI-1", "Review In Progress", BASE + timedelta(days=1))])

    assert len(merged) == 1
    assert merged[0].to_status == "Review In Progress"


def test_stale_older_event_does_not_overwrite_newer_stored_one(tmp_path):
    store = SubtaskTransitionStore(tmp_path / "store.xlsx")
    store.merge_and_save([_event("TI-1", "Review In Progress", BASE + timedelta(days=1))])
    # A re-run somehow re-fetches an older email for the same ticket.
    merged = store.merge_and_save([_event("TI-1", "Open", BASE)])

    assert len(merged) == 1
    assert merged[0].to_status == "Review In Progress"


def test_empty_store_reads_as_empty_list(tmp_path):
    store = SubtaskTransitionStore(tmp_path / "does_not_exist.xlsx")
    assert store.read_all() == []
