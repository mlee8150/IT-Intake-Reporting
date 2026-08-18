"""Panel 3 (CYCLE TIME: Where time goes / Working hours by team) — sub-task level.

Both outputs on this panel come from ONE table: per team, per sub-task
status (see vocabulary.SUBTASK_STATUSES). `compute_where_time_goes` builds
that table from transition emails (median days since the last transition
into each status); `compute_working_hours` is a pure rollup of that same
table — confirmed by the user: "Working hours" = Not Started + Review In
Progress summed per team, no separate Jira field involved.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime

from ..models import TransitionEvent
from ..vocabulary import SUBTASK_STATUSES, WORKING_HOURS_STATUSES


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


def compute_working_hours(hours_by_team_and_status: dict[str, dict[str, float]]) -> WorkingHoursResult:
    """`hours_by_team_and_status[team][status]` — in practice, pass in
    `WhereTimeGoesResult.median_days` directly (see module docstring)."""
    working_hours_by_team = {
        team: sum(
            hours for status, hours in statuses.items() if status in WORKING_HOURS_STATUSES
        )
        for team, statuses in hours_by_team_and_status.items()
    }
    total_hours_by_team = {
        team: sum(statuses.get(status, 0.0) for status in SUBTASK_STATUSES)
        for team, statuses in hours_by_team_and_status.items()
    }
    return WorkingHoursResult(
        working_hours_by_team=working_hours_by_team,
        total_hours_by_team=total_hours_by_team,
        total_working_hours=sum(working_hours_by_team.values()),
        total_hours=sum(total_hours_by_team.values()),
    )
