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

## 1a. Sub-task email scope vs. panel data sources — needs your call

You said sub-task emails are only used for **panels 2, 6, and 7**
(`panel2_throughput.py`, `panel6_aging.py`, `panel7_stalled.py`). But
`docs/DATA_SOURCES.md` and the current `pipeline.py` wiring say something
different:

| Panel | `DATA_SOURCES.md` says | `pipeline.py` currently does |
|---|---|---|
| 2 — Throughput trend | Automated transition emails | Derived from `backlog`, which is built from **parent-request** transition emails only (`parent_events`) |
| 3 — Where time goes / working hours | Automated transition emails, **sub-task level** | Uses `subtask_events` (the only panel currently wired to sub-task emails) |
| 6 — Aging | Jira dashboard | Uses `active_requests`, a parent-level JQL snapshot — no email data at all |
| 7 — Stalled | Jira dashboard | Uses `active_requests.updated` — no email data at all |

So right now sub-task emails feed panel 3, not 2/6/7, and panels 6/7 don't
use email data at all. Before I rewire anything, I need to know which is
actually right:

- Does panel 3 stop being sub-task-driven, and 2/6/7 start being? What
  should panel 3 use instead?
- For panels 6 and 7 to be sub-task-driven, they'd need either a JQL that
  returns active **sub-task** issues (not just parents), or would need to be
  computed purely from transition-event history instead of a live snapshot —
  which one matches how you actually want "aging" and "stalled" defined at
  the sub-task level (age/staleness of the sub-task itself, vs. of its
  parent request)?

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

## 6. "Stalled" definition (panel 7)

`panels/panel7_stalled.py` uses Jira's `updated` timestamp as "last activity."
If your workflow has automation/bots that bump `updated` without a real
reviewer touching the ticket, this will undercount stalled reviews. Flag if
there's a better signal (e.g. last comment, last status change) to use instead.
