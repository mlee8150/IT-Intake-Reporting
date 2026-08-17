"""Parses a Jira "ticket moved" notification email into TransitionEvent(s).

STATUS: rewritten against two real notification emails (Legal and IAM review
sub-tasks), transcribed from screenshots — not yet validated against raw
.eml/plain-text source. Whitespace, arrow-character encoding, and how Outlook
flattens the HTML card to `MailItem.Body` plain text could all differ in
practice from this transcription. Forward one real email (or `.Body` dumped
to a .txt file) and re-check this module against it — see
docs/OPEN_QUESTIONS.md #1. Wrong parsing here silently corrupts an
executive-facing report, so `parse_transition_email` raises instead of
guessing when no ticket key or no status-change line is found.

No real *parent-request* transition email has been seen yet — only sub-task
(review-team) emails. `is_parent_request` detection below (anything that
doesn't mention "Sub-task" is treated as a parent request) is still an
unvalidated guess for that side.

Two real notification shapes have been seen so far, both for sub-tasks:

Shape 1 — "<X> created a work item" / "<X> made N updates" digest, sent on
creation and/or transition. Each entry in the "Updates" section is an
actor + time line followed by the field that changed:

    Work item created
    Automation for Jira   03:57 PM PT
    Status: OPEN
    Work type: TI Legal Review
    ...
    Created: 20/Jul/26 3:57 PM

    Updates
    Automation for Jira   03:57 PM PT
    Parent: TI-82

    Jacob Gonzalez   03:58 PM PT
    Status: Open -> Review In Progress

    Jacob Gonzalez   03:58 PM PT
    Status: Review In Progress -> Awaiting Requestor Response

Shape 2 — "<X> commented" / "<X> changed the status to <Y>" digest, sent (at
least) on completion:

    Automation for Jira commented:
    May Lee, IAM Review Sub-task: TEST 27 - TI Intake has been completed...

    Automation for Jira changed the status to Completed.

Neither shape has a labeled "Team:" field (unlike the old guessed format);
the review team appears next to the word "Sub-task" instead (e.g. "Legal
review Sub-task", "IAM Review Sub-task"), or in the "Work type" field.

Real ticket titles (from a reference "Reviews Needing Follow-up" sheet, not
an email itself, but presumably reflecting the same source text) show
inconsistent spelling for both the word "Sub-task" and for "CyberArch" and
"Sub-ARB" specifically: "SubTask" (no hyphen), "Sub Task" (space), "CyberArk"
(typo), "CyberArchitecture", "Cyber Arch" (space), "SubARB" (no hyphen).
`_SUBTASK_MARKER_RE` and `_TEAM_ALIASES` below normalize these — treat that
alias list as provisional, not exhaustive; add to it as new spelling
variants turn up in real data rather than assuming this is the complete set.
"""
from __future__ import annotations

import re
from datetime import datetime, time

from ..models import TransitionEvent
from ..vocabulary import REVIEW_TEAMS
from .base import RawMessage

_TICKET_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]*-\d+)\b")

# "->" , the unicode arrow, or an unescaped HTML entity some clients leave
# in the plain-text body verbatim.
_ARROW = r"(?:->|→|&#x2192;)"
_STATUS_LINE_RE = re.compile(
    rf"^Status\s*:\s*(?:(?P<from>.+?)\s*{_ARROW}\s*)?(?P<to>.+?)\s*$", re.IGNORECASE
)
_WORK_TYPE_RE = re.compile(r"^Work type\s*:\s*(?P<value>.+?)\s*$", re.IGNORECASE)
_ACTOR_TIMESTAMP_RE = re.compile(
    r"^(?P<actor>[A-Za-z][\w'.-]*(?:\s+[A-Za-z][\w'.-]*)*)\s+"
    r"(?P<time>\d{1,2}:\d{2}\s*[AP]M(?:\s*[A-Z]{2,3})?)\s*$"
)
_CHANGED_STATUS_SENTENCE_RE = re.compile(
    r"(?P<actor>[A-Za-z][\w'.-]*(?:\s+[A-Za-z][\w'.-]*)*)\s+changed the status to\s+"
    r"(?P<to>[^.\n]+?)\.?\s*$",
    re.IGNORECASE,
)
# "Sub-task", "SubTask", "Sub Task" — hyphen, no separator, or a space.
_SUBTASK_MARKER = r"sub[\s-]?task"
_SUBTASK_MARKER_RE = re.compile(_SUBTASK_MARKER, re.IGNORECASE)

# Known real-world spelling variants for review-team names, mapped to the
# canonical spelling in vocabulary.REVIEW_TEAMS. Provisional — extend as new
# variants show up (see module docstring).
_TEAM_ALIASES: dict[str, str] = {t.lower(): t for t in REVIEW_TEAMS}
_TEAM_ALIASES.update(
    {
        "cyberark": "CyberArch",
        "cyberarchitecture": "CyberArch",
        "cyber arch": "CyberArch",
        "subarb": "Sub-ARB",
        "sub arb": "Sub-ARB",
    }
)
_TEAM_BY_LOWER = _TEAM_ALIASES

_SUBTASK_TEAM_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _TEAM_ALIASES) + r")\b.{0,20}?" + _SUBTASK_MARKER,
    re.IGNORECASE,
)


def parse_transition_email(message: RawMessage) -> list[TransitionEvent]:
    """One email can describe several status changes at once (the "Updates"
    digest) — this returns one TransitionEvent per change, oldest-looking-
    line-first (not guaranteed chronological; sort by `changed_at` if order
    matters)."""
    subject = message.subject
    body = message.body
    haystack = f"{subject}\n{body}"

    key_match = _TICKET_KEY_RE.search(subject) or _TICKET_KEY_RE.search(body)
    if not key_match:
        raise ValueError(
            f"Could not find a ticket key (e.g. 'TI-123') in email subject "
            f"{subject!r}. Parser assumptions are unvalidated — see this "
            "module's docstring."
        )
    ticket_key = key_match.group(1)

    is_parent = not _SUBTASK_MARKER_RE.search(haystack)
    review_team = _find_review_team(haystack, body)

    events: list[TransitionEvent] = []
    last_actor: str | None = None
    last_time_str: str | None = None

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        actor_match = _ACTOR_TIMESTAMP_RE.match(line)
        if actor_match:
            last_actor = actor_match.group("actor").strip()
            last_time_str = actor_match.group("time").strip()
            continue

        status_match = _STATUS_LINE_RE.match(line)
        if status_match:
            events.append(
                TransitionEvent(
                    ticket_key=ticket_key,
                    is_parent_request=is_parent,
                    review_team=review_team,
                    from_status=_normalize_status(status_match.group("from")),
                    to_status=_normalize_status(status_match.group("to")),
                    changed_at=_resolve_timestamp(message.received_at, last_time_str),
                    changed_by=last_actor,
                    raw_subject=subject,
                )
            )
            continue

        sentence_match = _CHANGED_STATUS_SENTENCE_RE.search(line)
        if sentence_match:
            events.append(
                TransitionEvent(
                    ticket_key=ticket_key,
                    is_parent_request=is_parent,
                    review_team=review_team,
                    from_status=None,
                    to_status=_normalize_status(sentence_match.group("to")),
                    changed_at=message.received_at,
                    changed_by=sentence_match.group("actor").strip(),
                    raw_subject=subject,
                )
            )

    if not events:
        raise ValueError(
            f"Found ticket key {ticket_key!r} but no 'Status: ...' or 'changed the "
            f"status to ...' line in the body of {subject!r}. Parser assumptions are "
            "unvalidated — see this module's docstring."
        )

    return events


def _find_review_team(haystack: str, body: str) -> str | None:
    team_match = _SUBTASK_TEAM_RE.search(haystack)
    if team_match:
        return _TEAM_BY_LOWER[team_match.group(1).lower()]

    for raw_line in body.splitlines():
        work_type_match = _WORK_TYPE_RE.match(raw_line.strip())
        if not work_type_match:
            continue
        value_lower = work_type_match.group("value").lower()
        for lower_name, canonical in _TEAM_BY_LOWER.items():
            if lower_name in value_lower:
                return canonical
    return None


def _normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    # "OPEN" (all-caps status chip) -> "Open", to match the mixed-case
    # spelling used everywhere else ("Review In Progress", "Completed", ...).
    return value.title() if value.isupper() else value


def _resolve_timestamp(received_at: datetime, time_str: str | None) -> datetime:
    if time_str is None:
        return received_at
    parsed_time = _parse_time_of_day(time_str)
    if parsed_time is None:
        return received_at
    return received_at.replace(
        hour=parsed_time.hour, minute=parsed_time.minute, second=0, microsecond=0
    )


_TIME_OF_DAY_RE = re.compile(r"(?P<hm>\d{1,2}:\d{2}\s*[AP]M)", re.IGNORECASE)


def _parse_time_of_day(time_str: str) -> time | None:
    # Extract just the "H:MM AM/PM" part, discarding any trailing timezone
    # abbreviation like "PT" — we keep received_at's own tzinfo rather than
    # trying to convert, since only the offset (not the IANA zone) is
    # knowable from "PT" alone.
    match = _TIME_OF_DAY_RE.search(time_str.strip())
    if not match:
        return None
    try:
        return datetime.strptime(match.group("hm"), "%I:%M %p").time()
    except ValueError:
        return None
