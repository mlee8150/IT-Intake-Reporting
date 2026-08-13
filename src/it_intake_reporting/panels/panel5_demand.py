"""Panel 5 (DEMAND & RISK: Where demand comes from) — active parent requests
by requesting function, rolled up from Jira's department field via the
department -> function mapping.
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
