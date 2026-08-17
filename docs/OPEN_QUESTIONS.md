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
| 7 — Stalled | **Sub-task (changed)** | Confirmed against "Reviews Needing Follow-up" — a flat list of individual review sub-tasks with their own status/last-updated/days-since-update. `panel7_stalled.py` and `pipeline.py` have been rewired: `compute_stalled` now takes the same `latest_subtask_transition` list panel 3 uses (one TransitionEvent per open sub-task, its most recent status change), instead of the parent-level Jira snapshot. |

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

## 2. Jira custom field IDs

`.env` needs three custom field IDs that only exist in your Jira instance:

- `JIRA_FIELD_DEPARTMENT` — the requesting department (panel 5)
- `JIRA_FIELD_REVIEW_TEAM` — CyberArch / TPRM / Legal / IAM / AI / Sub-ARB (panels 3, 6, 7)
- `JIRA_FIELD_EXEC_CRITICAL` — the flag behind the "Exec-critical requests open" headline stat

Find them via Jira Settings > Issues > Custom fields, or `GET /rest/api/3/field`.

## 3. Where "Working Hours" (panel 3) actually comes from

The template shows per-team hour totals (CyberArch 82 hrs, etc.) footnoted as
"Working Hours = Not Started + Review In Progress." That's a rollup rule
(implemented in `panels/panel3_review_effort.py::compute_working_hours`), but
the *source number per sub-task* — is it a time-tracking field, an estimate
field, or something else — isn't identified yet. If it's a Jira field, set
`JIRA_FIELD_HOURS`; if it's tracked elsewhere (e.g. entered manually in the
"previous decks" Excel you mentioned), the pipeline needs a different input
for it — let's decide once you confirm the source.

## 4. Confirm the workflow status vocabulary

`src/it_intake_reporting/vocabulary.py` hardcodes status/team names lifted
from the template's own (partly estimated) chart data — e.g. the balance-bridge
statuses in `panel1_backlog.py::STATUS_TO_BUCKET` ("Completed", "Not Approved",
"Cancelled", "On Hold"). If your real workflow uses different status labels,
these need updating — they're deliberately centralized so that's a one-file change.

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

Still unconfirmed: the exact inclusion/threshold rule behind "Reviews
Needing Follow-up" isn't fully known — its `Days` column included values
below the 7-day `STALLED_THRESHOLD_DAYS` cutoff currently used in code (e.g.
5 days), suggesting that sheet may list *all* open sub-tasks with their age
rather than only ones past a stalled threshold. If panel 7's tile is meant
to match that sheet's row count exactly, confirm whether 7 days is really
the right cutoff.
