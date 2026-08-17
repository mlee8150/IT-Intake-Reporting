"""Parser tests against the two real sub-task notification emails we have
transcriptions of (see transition_parser.py's docstring for the originals).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from it_intake_reporting.mailbox.base import RawMessage
from it_intake_reporting.mailbox.transition_parser import parse_transition_email

RECEIVED_AT = datetime(2026, 7, 20, 22, 0, tzinfo=timezone.utc)  # 3:00 PM PT-ish


def _msg(subject: str, body: str) -> RawMessage:
    return RawMessage(subject=subject, body=body, received_at=RECEIVED_AT, sender="jira@example.com")


def test_work_item_created_digest_with_multiple_updates():
    message = _msg(
        "[JIRA] (TI-85) Legal review Sub-task: TEST 30 - TI Intake",
        """
        Technology Intake / TI-85
        Legal review Sub-task: TEST 30 - TI Intake

        Work item created
        Automation for Jira 03:57 PM PT
        Status: OPEN
        Work type: TI Legal Review
        Assignee: Jacob Gonzalez
        Priority: Low
        Reporter: May Lee
        Created: 20/Jul/26 3:57 PM

        Updates
        Automation for Jira 03:57 PM PT
        Parent: TI-82

        Jacob Gonzalez 03:58 PM PT
        Status: Open -> Review In Progress

        Jacob Gonzalez 03:58 PM PT
        Status: Review In Progress -> Awaiting Requestor Response
        """,
    )

    events = parse_transition_email(message)

    assert [e.to_status for e in events] == [
        "Open",
        "Review In Progress",
        "Awaiting Requestor Response",
    ]
    assert [e.from_status for e in events] == [None, "Open", "Review In Progress"]
    assert all(e.ticket_key == "TI-85" for e in events)
    assert all(e.is_parent_request is False for e in events)
    assert all(e.review_team == "Legal" for e in events)

    created_event, first_move, second_move = events
    assert created_event.changed_by == "Automation for Jira"
    assert created_event.changed_at.hour == 15 and created_event.changed_at.minute == 57
    assert first_move.changed_by == "Jacob Gonzalez"
    assert first_move.changed_at.minute == 58
    assert second_move.changed_by == "Jacob Gonzalez"


def test_commented_and_changed_status_digest():
    message = _msg(
        "TI-69 TEST 27 - TI Intake",
        """
        Automation for Jira commented:
        May Lee, IAM Review Sub-task: TEST 27 - TI Intake has been completed and is
        now moving to the next phase of the technology intake process.

        Automation for Jira changed the status to Completed.

        Automation for Jira commented:
        May Lee, TEST 27 - TI Intake has been completed. You can now move forward
        with onboarding your application.
        """,
    )

    events = parse_transition_email(message)

    assert len(events) == 1
    event = events[0]
    assert event.ticket_key == "TI-69"
    assert event.is_parent_request is False
    assert event.review_team == "IAM"
    assert event.from_status is None
    assert event.to_status == "Completed"
    assert event.changed_by == "Automation for Jira"
    assert event.changed_at == RECEIVED_AT


@pytest.mark.parametrize(
    ("subject", "expected_team"),
    [
        ("[JIRA] (TI-207) CyberArch Sub-Task: (Octopus) - IT", "CyberArch"),
        ("[JIRA] (TI-144) CyberArk Review Sub-Task: Articulate - IT", "CyberArch"),
        ("[JIRA] (TI-194) CyberArchitecture Review Sub-Task:", "CyberArch"),
        ("[JIRA] (TI-181) Cyber Arch Review Sub-Task: Anthropic Claude -", "CyberArch"),
        ("[JIRA] (TI-143) CyberArch Review SubTask: Serval - IT", "CyberArch"),
        ("[JIRA] (TI-213) SubARB Review Sub Task: POC Supply Chain", "Sub-ARB"),
    ],
)
def test_recognizes_real_world_team_spelling_variants(subject, expected_team):
    message = _msg(subject, "Status: Open -> Review In Progress")

    events = parse_transition_email(message)

    assert events[0].is_parent_request is False
    assert events[0].review_team == expected_team


def test_raises_when_no_ticket_key_found():
    message = _msg("no key here", "Status: Open")
    with pytest.raises(ValueError, match="ticket key"):
        parse_transition_email(message)


def test_raises_when_no_status_line_found():
    message = _msg("TI-1 update", "Parent: TI-2")
    with pytest.raises(ValueError, match="Status"):
        parse_transition_email(message)
