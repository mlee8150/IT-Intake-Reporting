# Open questions

This pipeline is fully wired end-to-end (see `tests/test_pipeline_smoke.py` for a
passing run against synthetic data) but several pieces are built against
assumptions that need to be checked against your real Jira instance and mailbox
before you can trust the numbers in a real deck. In rough priority order:

## 1. A real sample transition email

`src/it_intake_reporting/mailbox/transition_parser.py` currently expects:

```
Subject: [PROJ-123] Status changed: Review In Progress -> Conditional Approval

Body:
  Issue Type: Parent Request        (or "Sub-task")
  Team: CyberArch                   (sub-tasks only)
  Status: Review In Progress -> Conditional Approval
  Changed By: Jane Doe
```

This is a guess at what a Jira Automation "send email on transition" rule
typically produces — it has not been checked against a real email. **Forward
one real transition-notification email** (redact ticket content if needed,
keep the subject/body structure intact) and this parser should be rewritten
to match exactly, not patched around.

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
