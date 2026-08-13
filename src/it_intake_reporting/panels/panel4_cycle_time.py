"""Panel 4 (CYCLE TIME: Cycle time trend) — median days to complete intake, 12 months.

Cycle time = Jira `created` to the transition into "Completed", at the
parent-request level. This month's median comes from live data; older months
come from the rolling history workbook.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date

from ..models import WeeklySnapshot

TREND_MONTHS = 12


@dataclass(frozen=True)
class MonthPoint:
    month: str  # "YYYY-MM"
    median_days: float


def median_cycle_time_days(completed_this_period: list[tuple[date, date]]) -> float:
    """Each tuple is (created_date, completed_date) for one parent request completed this period."""
    if not completed_this_period:
        return 0.0
    days = [(completed - created).days for created, completed in completed_this_period]
    return round(statistics.median(days), 1)


def compute_cycle_time_trend(
    history: list[WeeklySnapshot],
    this_month: str,
    this_month_median_days: float,
    months: int = TREND_MONTHS,
) -> list[MonthPoint]:
    by_month: dict[str, list[float]] = {}
    for snapshot in history:
        month_key = snapshot.week_ending.strftime("%Y-%m")
        by_month.setdefault(month_key, []).append(snapshot.median_cycle_time_days)

    # Averaging the stored weekly medians is an approximation of the true
    # monthly median (we don't retain every individual cycle-time sample,
    # only each week's median) — close enough for a trend line, not exact.
    monthly_medians = {
        month: round(statistics.mean(values), 1) for month, values in by_month.items()
    }
    monthly_medians[this_month] = this_month_median_days

    points = [MonthPoint(month, median) for month, median in monthly_medians.items()]
    points.sort(key=lambda p: p.month)
    return points[-months:]
