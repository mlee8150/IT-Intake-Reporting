"""Panel 3 (CYCLE TIME: Where time goes / Working hours by team) — sub-task level.

Two separate outputs live on this panel, both derived purely from
transition-email timestamps — no Jira hours field needed (see
docs/OPEN_QUESTIONS.md #3, resolved: per the report owner, since we know
when a sub-task flips to another status, the elapsed time since that flip
*is* the hours figure):
  - "Where time goes": median days a sub-task has sat in its current status,
    by team and status.
  - "Working hours by team": elapsed hours since each open sub-task's latest
    transition, summed by team — split into "working" (Not Started + Review
    In Progress) vs. all statuses.

Both take the same `latest_transition_per_subtask` list (one TransitionEvent
per open sub-task: the transition that put it into its *current* status).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime

from ..models import TransitionEvent
from ..vocabulary import WORKING_HOURS_STATUSES


@dataclass(frozen=True)
class WhereTimeGoesResult:
    # median_days[team][status] = median days sub-tasks on that team have
    # been sitting in that status, as of `as_of`.
    median_days: dict[str, dict[str, float]]


def compute_where_time_goes(
    latest_transition_per_subtask: list[TransitionEvent], as_of: datetime
) -> WhereTimeGoesResult:
    """`latest_transition_per_subtask` must contain exactly one event per open
    sub-task: the transition that put it into its *current* status."""
    days_by_team_status: dict[str, dict[str, list[float]]] = {}
    for event in latest_transition_per_subtask:
        if event.is_parent_request or event.review_team is None:
            continue
        days_open = (as_of - event.changed_at).total_seconds() / 86400
        team_bucket = days_by_team_status.setdefault(event.review_team, {})
        team_bucket.setdefault(event.to_status, []).append(days_open)

    median_days = {
        team: {
            status: round(statistics.median(days_list), 1)
            for status, days_list in statuses.items()
        }
        for team, statuses in days_by_team_status.items()
    }
    return WhereTimeGoesResult(median_days=median_days)


@dataclass(frozen=True)
class WorkingHoursResult:
    working_hours_by_team: dict[str, float]
    total_hours_by_team: dict[str, float]
    total_working_hours: float
    total_hours: float


def compute_working_hours(
    latest_transition_per_subtask: list[TransitionEvent], as_of: datetime
) -> WorkingHoursResult:
    """Hours = elapsed time since each open sub-task's latest transition
    (i.e. time already spent in its current status), summed by team."""
    working_hours_by_team: dict[str, float] = {}
    total_hours_by_team: dict[str, float] = {}
    for event in latest_transition_per_subtask:
        if event.is_parent_request or event.review_team is None:
            continue
        hours = (as_of - event.changed_at).total_seconds() / 3600
        total_hours_by_team[event.review_team] = total_hours_by_team.get(event.review_team, 0.0) + hours
        if event.to_status in WORKING_HOURS_STATUSES:
            working_hours_by_team[event.review_team] = (
                working_hours_by_team.get(event.review_team, 0.0) + hours
            )
    return WorkingHoursResult(
        working_hours_by_team=working_hours_by_team,
        total_hours_by_team=total_hours_by_team,
        total_working_hours=sum(working_hours_by_team.values()),
        total_hours=sum(total_hours_by_team.values()),
    )
