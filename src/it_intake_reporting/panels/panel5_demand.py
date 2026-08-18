"""Panel 5 (DEMAND & RISK: Where demand comes from) — lifetime parent request
volume by requesting function, rolled up from Jira's department field via
the department -> function mapping.

Deliberately lifetime, not active-only: `requests` here is expected to be
every parent request ever created (any status), not the same active-only
population panels 1 and 6 use — see pipeline.py's `lifetime_requests` and
docs/OPEN_QUESTIONS.md. The report owner may want this switched to
active-only later; if so, this function doesn't change, just which request
list pipeline.py passes in.
"""
from __future__ import annotations

from collections import Counter

from ..mapping import DepartmentMapping
from ..models import JiraRequest


def compute_demand_by_function(
    requests: list[JiraRequest], mapping: DepartmentMapping
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for request in requests:
        counts[mapping.function_for(request.department)] += 1
    return dict(counts)
