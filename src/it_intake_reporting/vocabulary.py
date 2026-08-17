"""
Domain vocabulary: review teams, sub-task statuses, balance-bridge event
types, demand-source functions, aging buckets.

DEMAND_FUNCTIONS is confirmed real (see below). Everything else here still
comes from the deck template's own sample chart data, used as a default —
still needs reconciling against the real Jira instance's actual
status/team/component names. See docs/OPEN_QUESTIONS.md.
"""
from __future__ import annotations

# Review teams (panel 3 "Where time goes", panel 6 "Aging", panel 7 "Stalled").
REVIEW_TEAMS = ["Sub-ARB", "AI", "TPRM", "CyberArch", "Legal", "IAM"]

# Sub-task statuses that make up "working hours" per team (panel 3).
# Working Hours = NOT_STARTED + REVIEW_IN_PROGRESS; the other statuses are
# shown in the stacked bar but excluded from the working-hours total.
SUBTASK_STATUSES = [
    "Not Started",
    "On Hold",
    "Review In Progress",
    "Awaiting Requestor",
    "Conditional Approval",
]
WORKING_HOURS_STATUSES = {"Not Started", "Review In Progress"}

# Parent-request balance-bridge event types (panel 1: opening -> closing balance).
BALANCE_BRIDGE_EVENTS = [
    "newly_opened",
    "re_opened",
    "completed",
    "not_approved",
    "cancelled",
    "on_hold",
]

# Demand-source functions after rolling department -> function (panel 5).
# Confirmed real (Appendix B, "Department to Function Mapping" — the 22 real
# Requesting Department dropdown values roll up to these 5).
DEMAND_FUNCTIONS = ["G&A", "Manufacturing & Operations", "R&D", "Revenue", "Others"]

# Aging buckets, in days (panel 6).
AGING_BUCKETS = [(0, 30), (31, 60), (61, 90), (91, None)]
