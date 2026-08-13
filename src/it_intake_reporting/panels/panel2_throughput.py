"""Panel 2 (TICKET FLOW: Throughput trend) — opened vs closed, last 12 weeks.

This week's counts come from transition emails; older weeks come from the
rolling history workbook (mailbox retention won't reliably cover 12 weeks).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..models import WeeklySnapshot

TREND_WEEKS = 12


@dataclass(frozen=True)
class WeekPoint:
    week_ending: date
    opened: int
    closed: int


def compute_throughput_trend(
    history: list[WeeklySnapshot],
    this_week_ending: date,
    this_week_opened: int,
    this_week_closed: int,
    weeks: int = TREND_WEEKS,
) -> list[WeekPoint]:
    points = [
        WeekPoint(s.week_ending, s.opened, s.closed)
        for s in history
        if s.week_ending != this_week_ending
    ]
    points.append(WeekPoint(this_week_ending, this_week_opened, this_week_closed))
    points.sort(key=lambda p: p.week_ending)
    return points[-weeks:]
