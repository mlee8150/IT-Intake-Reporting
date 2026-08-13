# Data sources and panel mapping

The deck template (`templates/Technology_Intake_Weekly_Exec_Summary.pptx`) is a single slide
with 4 headline stats and 7 numbered panels, grouped into 3 sections. This mapping was
confirmed against the template's own speaker notes and chart data.

## Headline stats (top of slide)

| Stat | Source |
|---|---|
| Open requests (active) | Panel 1 (derived, must equal Panel 1's closing balance) |
| Requests resolved this week | Panel 1 (derived, "Completed" count for the week) |
| Open more than 90 days | Panel 6 (derived, `> 90 days` bucket) |
| Exec-critical requests open | Jira dashboard, compared against last week's deck |

## Section: TICKET FLOW

| # | Panel | Source | Notes |
|---|---|---|---|
| 1 | Backlog this week (parent requests) | Automated transition emails | Opening balance + newly opened + re-opened − completed − not approved − cancelled − on hold = closing balance. **Closing balance must be validated against the Jira dashboard's open-count** before the deck is trusted. |
| 2 | Throughput trend — opened vs closed (last 12 weeks) | Automated transition emails | Rolling 12-week window. Kept in the rolling history workbook (see below) since transition emails older than the mailbox retention window are not re-derivable. |

## Section: CYCLE TIME

| # | Panel | Source | Notes |
|---|---|---|---|
| 3 | Where time goes — by review team, working hours (sub-tasks) | Automated transition emails + rolling history workbook | Sub-task level, not parent-request level. "Working Hours" = time in Not Started + Review In Progress states, by review team. |
| 4 | Cycle time trend — median days (last 12 months) | Automated transition emails + rolling history workbook | Parent-request level. 12 months of history won't fit in mailbox retention — the rolling workbook is the source of truth for anything older than the current quarter. |

## Section: DEMAND & RISK

| # | Panel | Source | Notes |
|---|---|---|---|
| 5 | Where demand comes from (by function) | Jira dashboard + department→function mapping | Jira gives requesting department; the mapping table rolls that up to G&A / Revenue / R&D / Mfg & Ops etc. |
| 6 | Aging requests (active), by age bucket | Jira dashboard | 0-30 / 31-60 / 61-90 / >90 days, by review team. |
| 7 | Stalled reviews (no update in 7+ days) | Jira dashboard | |

## Open items needing real data before these are more than scaffolding

See [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).
