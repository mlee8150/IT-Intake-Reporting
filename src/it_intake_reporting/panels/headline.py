"""The 4 headline stat tiles at the top of the slide, each with a vs-last-week delta."""
from __future__ import annotations

from dataclasses import dataclass

from ..models import WeeklySnapshot


@dataclass(frozen=True)
class HeadlineStats:
    open_requests_active: int
    open_requests_delta: int
    resolved_this_week: int
    resolved_delta: int
    aging_90_plus: int
    aging_delta: int
    exec_critical_open: int
    exec_critical_delta: int


def compute_headline_stats(
    open_requests_active: int,
    resolved_this_week: int,
    aging_90_plus: int,
    exec_critical_open: int,
    previous_week: WeeklySnapshot | None,
) -> HeadlineStats:
    prev = previous_week
    return HeadlineStats(
        open_requests_active=open_requests_active,
        open_requests_delta=open_requests_active - (prev.open_requests_active if prev else open_requests_active),
        resolved_this_week=resolved_this_week,
        resolved_delta=resolved_this_week - (prev.resolved_this_week if prev else resolved_this_week),
        aging_90_plus=aging_90_plus,
        aging_delta=aging_90_plus - (prev.aging_90_plus if prev else aging_90_plus),
        exec_critical_open=exec_critical_open,
        exec_critical_delta=exec_critical_open - (prev.exec_critical_open if prev else exec_critical_open),
    )
