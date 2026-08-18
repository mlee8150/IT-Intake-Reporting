# Open questions

This pipeline is fully wired end-to-end (see `tests/test_pipeline_smoke.py` for a
passing run against synthetic data) but several pieces are built against
assumptions that need to be checked against your real Jira instance and mailbox
before you can trust the numbers in a real deck. In rough priority order:

## 1. A real sample transition email

`src/it_intake_reporting/mailbox/transition_parser.py` was rewritten against
two real sub-task notification emails (Legal and IAM review sub-tasks,
transcribed from screenshots — see the module docstring for the originals):

- A "work item created" + "Updates" digest, sent on creation and on each
  status move. One email can contain several status changes; the parser now
  returns `list[TransitionEvent]` per email instead of a single event.
- A "commented" + "changed the status to X" digest, sent at least on
  sub-task completion.

Both are **sub-task** (review-team) emails. **No real parent-request
transition email has been seen yet** — `is_parent_request` detection (true
whenever "Sub-task" doesn't appear anywhere in the subject/body) is still an
unvalidated guess for that side. Forward one real parent-request transition
email to close this out.

Also still unvalidated: this was built from screen photos, not the raw
`.eml`/plain-text source, so exact whitespace and arrow-character encoding
(`->` vs `→` vs a literal `&#x2192;`) may not match what `MailItem.Body`
actually contains. If the parser starts silently dropping updates once
connected to a real mailbox, this is the first place to check — dump a raw
`.Body` to a `.txt` file and diff it against the shapes in the module
docstring.

## 1a. Sub-task email scope vs. panel data sources — RESOLVED

Was flagged as a conflict: `docs/DATA_SOURCES.md`/`pipeline.py` had panel 3
as the only sub-task-driven panel, while the report owner said sub-tasks
drive panels 2, 6, and 7. Settled against two real reference sheets from the
actual reporting workbook ("TI Intake" aging sheet and "Reviews Needing
Follow-up"):

| Panel | Level | Status |
|---|---|---|
| 2 — Throughput trend | Parent-request (unchanged) | Confirmed — no sub-task source exists for this; stays driven by `parent_events` |
| 3 — Where time goes / working hours | Sub-task (unchanged) | Already correct |
| 6 — Aging | Parent-request (unchanged) | Confirmed against the "TI Intake" aging sheet (0-30/31-60/61-90/90+ day buckets, no per-sub-task breakdown) |
| 7 — Stalled | **Sub-task (changed)** | Confirmed against "Reviews Needing Follow-up" — a flat list of individual review sub-tasks with their own status/last-updated/days-since-update. `panel7_stalled.py` and `pipeline.py` have been rewired: `compute_stalled` now takes the same `latest_subtask_transition` list panel 3 uses (one TransitionEvent per open sub-task, its most recent status change), instead of the parent-level Jira snapshot — and counts every open sub-task with no day-count filter (see #6). |

This also resolves #6 below — using each sub-task's transition timestamp
sidesteps the "bot bumps `updated`" risk entirely, since it's driven by an
actual status change, not a raw field touch.

**New gap this surfaced, still open:** `latest_subtask_transition` is built
only from transition emails fetched for the current run's ~7-day window
(see `pipeline._fetch_transition_events`). A sub-task that has been
genuinely stalled for longer than that — no transition at all in the fetch
window — won't appear in `subtask_events` and is therefore invisible to
both panel 3 and (now) panel 7, not merely undercounted. The "Reviews
Needing Follow-up" sheet, by contrast, appears to reflect *all* currently
open sub-tasks regardless of when they last moved. Two ways to close this,
need your call:

- Widen the transition-email fetch window specifically for computing
  "latest transition per sub-task" (fetch further back than 7 days, keeping
  only the newest event per ticket) — simplest, but re-processes more email
  each run as backlog grows.
- Persist a running "latest known transition per sub-task" store across
  runs (same idea as the rolling history workbook, but keyed by ticket
  instead of by week) — more moving parts, but stays cheap per run
  regardless of how old the oldest stalled ticket gets.

## 1b. Panel 5 population — lifetime, not active-only (decided, revisit later)

Panel 5 ("Where demand comes from") counts *lifetime* parent-request volume
(every request ever created, any status), not the active-only population
panels 1 and 6 use — a deliberate choice by the report owner, made when
reconciling against the real "Request Volume by Department" reference sheet
(which includes Completed/Cancelled/Not Approved/etc. rows, not just open
ones). `pipeline.py` fetches this as a second, separate Jira query
(`jira_jql_lifetime_requests` / `JIRA_JQL_LIFETIME_REQUESTS`, no
`statusCategory` filter) — `active_requests` (used by panels 1 and 6, and
the exec-critical headline stat) is untouched.

**Flagged for a possible future revisit:** the report owner may want this
switched to active-only later, to show current demand pressure rather than
historical volume. If so, `panel5_demand.py::compute_demand_by_function`
itself doesn't need to change — just point `pipeline.py` at `active_requests`
instead of `lifetime_requests`.

## 2. Jira custom field IDs — RESOLVED down to two

`.env` needs two custom field IDs that only exist in your Jira instance:

- `JIRA_FIELD_DEPARTMENT` — the requesting department (panel 5)
- `JIRA_FIELD_EXEC_CRITICAL` — the flag behind the "Exec-critical requests open" headline stat

Find them via Jira Settings > Issues > Custom fields, or `GET /rest/api/3/field`.

There is no `JIRA_FIELD_REVIEW_TEAM` — per the report owner, review team
isn't a Jira field at all, it's embedded in the sub-task's own name (e.g.
"Legal review Sub-task"), which `transition_parser.py` already extracts for
panels 3 and 7. It turned out panel 6 didn't need a team dimension either —
`AgingResult.by_team_and_bucket` was computed but never actually read by the
deck (only `total_by_bucket`), so it, `JiraRequest.review_team`, and the
now-pointless `JiraRequest.raw_fields` escape hatch have all been removed.

The six real team names, for reference: **CyberArch, AI, Legal, IAM,
Sub-ARB, TPRM** — matches `vocabulary.REVIEW_TEAMS`. Real sub-task titles
spell these inconsistently (see `transition_parser.py`'s `_TEAM_ALIASES`),
which the parser now tolerates.

## 3. Where "Working Hours" (panel 3) actually comes from — RESOLVED

No Jira hours field needed. Per the report owner: since we know when a
sub-task flips to another status, the elapsed time since that flip *is* the
hours figure — no separate time-tracking/estimate field to look up.

`compute_working_hours` (`panels/panel3_review_effort.py`) now takes the
same `latest_transition_per_subtask` list "Where time goes" uses, and sums
`(as_of - event.changed_at)` in hours per team — split into "working"
(Not Started + Review In Progress) vs. all statuses, same rollup rule as
before. `JIRA_FIELD_HOURS` has been removed from `Settings`/`.env.example`
as dead config.

Inherits the same caveat as #1a: only sees sub-tasks that appear in the
current run's fetched transition emails, so a sub-task with no activity in
that window is invisible to this hours total too, not just panel 7.

## 4. Confirm the workflow status vocabulary

`src/it_intake_reporting/vocabulary.py` hardcodes status/team names lifted
from the template's own (partly estimated) chart data — e.g. the balance-bridge
statuses in `panel1_backlog.py::STATUS_TO_BUCKET` ("Completed", "Not Approved",
"Cancelled", "On Hold"). If your real workflow uses different status labels,
these need updating — they're deliberately centralized so that's a one-file change.

**Demand functions (panel 5) — RESOLVED.** Confirmed real from "Appendix B —
Department to Function Mapping": the 22 real Requesting Department dropdown
values roll up to 5 functions — G&A, Manufacturing & Operations, R&D,
Revenue, Others (not the 4 guessed functions previously in
`DEMAND_FUNCTIONS`, and "Others" wasn't in the guess at all).
`config/department_mapping.example.csv` now has the real 22 rows;
`vocabulary.DEMAND_FUNCTIONS` updated to match. Copy that file to
`config/department_mapping.csv` (gitignored) to use it for real —
`department_mapping.py` will raise a clear error on any request whose real
Jira department value isn't one of these 22.

The two real sub-task emails (see #1) showed **Open, Review In Progress,
Awaiting Requestor Response, Completed** — none of which exactly match
`SUBTASK_STATUSES` in `vocabulary.py` ("Not Started", "On Hold", "Review In
Progress", "Awaiting Requestor", "Conditional Approval"). That list still
needs to be reconciled once you can pull (or forward) the full status set
for a sub-task workflow, not just the ones these two example tickets
happened to pass through.

## 5. Graph API migration (when you're ready)

You asked how hard switching from Outlook desktop (COM) to Microsoft Graph
would be later: not hard, by design. `mailbox/base.py` defines the interface
both backends implement; `mailbox/graph.py` is a stub with the concrete steps
(Azure app registration, `Mail.Read` application permission, MSAL token
acquisition) already written up. Implementing it and changing one constructor
call in `cli.py` is the entire migration — nothing in the parser or panels
needs to change.

## 6. "Stalled" definition (panel 7) — RESOLVED, see #1a

Now uses each sub-task's own latest status-transition timestamp instead of
the parent's raw Jira `updated` field, closing the "bot bumps `updated`"
risk this item used to flag. The remaining open piece (transition emails
outside the fetch window making long-stalled tickets invisible) is tracked
under #1a, not here.

Per the report owner, there's no separate day-count threshold at all —
`compute_stalled` no longer filters by age; it counts every open sub-task
the pipeline currently knows about, by team, matching whatever the data
shows (the same shape as the "Reviews Needing Follow-up" sheet, which
included rows as young as 5 days). `STALLED_THRESHOLD_DAYS` has been removed
from `vocabulary.py` as dead code.
