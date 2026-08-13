"""Parses a Jira "ticket moved" notification email into a TransitionEvent.

STATUS: best-effort default, NOT validated against a real sample email yet.
See docs/OPEN_QUESTIONS.md — forward one real transition email (with any
sensitive ticket content redacted, format intact) and this file should be
rewritten against it rather than trusted as-is. Wrong parsing here silently
corrupts an executive-facing report, so `parse_transition_email` raises
instead of guessing when a required field is missing — do not change that
without a real sample to justify it.

Assumed format (typical of a Jira Automation "send email on transition" rule):

  Subject: [PROJ-123] Status changed: Review In Progress -> Conditional Approval

  Body (plain text), one field per line, in any order:
    Issue Type: Parent Request        (or "Sub-task")
    Team: CyberArch                   (present for sub-tasks; absent for parents)
    Status: Review In Progress -> Conditional Approval
    Changed By: Jane Doe
"""
from __future__ import annotations

import re

from ..models import TransitionEvent
from .base import RawMessage

_TICKET_KEY_RE = re.compile(r"\[([A-Z][A-Z0-9]+-\d+)\]")
_STATUS_RE = re.compile(
    r"Status:\s*(?:(?P<from>[^\n\r]+?)\s*->\s*)?(?P<to>[^\n\r]+)", re.IGNORECASE
)
_ISSUE_TYPE_RE = re.compile(r"Issue Type:\s*([^\n\r]+)", re.IGNORECASE)
_TEAM_RE = re.compile(r"Team:\s*([^\n\r]+)", re.IGNORECASE)
_CHANGED_BY_RE = re.compile(r"Changed By:\s*([^\n\r]+)", re.IGNORECASE)

PARENT_ISSUE_TYPE_MARKERS = {"parent request", "parent"}


def parse_transition_email(message: RawMessage) -> TransitionEvent:
    key_match = _TICKET_KEY_RE.search(message.subject) or _TICKET_KEY_RE.search(message.body)
    if not key_match:
        raise ValueError(
            f"Could not find a ticket key (e.g. 'PROJ-123') in email subject "
            f"{message.subject!r}. Parser assumptions are unvalidated — see this "
            "module's docstring."
        )

    status_match = _STATUS_RE.search(message.subject) or _STATUS_RE.search(message.body)
    if not status_match:
        raise ValueError(
            f"Could not find a 'Status: X -> Y' line for {key_match.group(1)}. "
            "Parser assumptions are unvalidated — see this module's docstring."
        )

    issue_type_match = _ISSUE_TYPE_RE.search(message.body)
    is_parent = True
    if issue_type_match:
        is_parent = issue_type_match.group(1).strip().lower() in PARENT_ISSUE_TYPE_MARKERS

    team_match = _TEAM_RE.search(message.body)
    changed_by_match = _CHANGED_BY_RE.search(message.body)

    return TransitionEvent(
        ticket_key=key_match.group(1),
        is_parent_request=is_parent,
        review_team=team_match.group(1).strip() if team_match else None,
        from_status=(status_match.group("from") or "").strip() or None,
        to_status=status_match.group("to").strip(),
        changed_at=message.received_at,
        changed_by=changed_by_match.group(1).strip() if changed_by_match else None,
        raw_subject=message.subject,
    )
