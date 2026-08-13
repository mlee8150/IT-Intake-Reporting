"""Dataclasses shared across the mailbox, Jira, and panel-computation layers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class TransitionEvent:
    """One ticket moving from one workflow status to another.

    Produced by mailbox.transition_parser from a single Jira notification email.
    """

    ticket_key: str
    is_parent_request: bool
    review_team: str | None
    from_status: str | None
    to_status: str
    changed_at: datetime
    changed_by: str | None
    raw_subject: str


@dataclass(frozen=True)
class JiraRequest:
    """One parent request as currently reflected in Jira (a dashboard snapshot row)."""

    key: str
    summary: str
    status: str
    status_category: str
    department: str
    review_team: str | None
    created: datetime
    updated: datetime
    is_exec_critical: bool
    # Full raw Jira `fields` payload, for reaching custom fields (e.g. an
    # hours-estimate field for panel 3) whose field id isn't known yet — see
    # docs/OPEN_QUESTIONS.md.
    raw_fields: dict | None = None


@dataclass(frozen=True)
class WeeklySnapshot:
    """One row of the rolling history workbook — this week's totals for the trend panels
    and headline stats (the headline stats need last week's row for their deltas)."""

    week_ending: date
    opened: int
    closed: int
    median_cycle_time_days: float
    working_hours_by_team: dict[str, float]
    open_requests_active: int
    resolved_this_week: int
    aging_90_plus: int
    exec_critical_open: int
