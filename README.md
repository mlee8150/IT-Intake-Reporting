# IT Intake Reporting

Generates the weekly "Technology Intake — Weekly Executive Summary" deck from:

- Automated Jira "ticket moved" emails landing in a shared mailbox
- The Jira dashboard (via the REST API)
- A department -> function mapping

See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) for exactly which of the
deck's 7 panels pulls from which source, [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for how the code is organized, and **[docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md)
for what still needs to be confirmed against your real Jira/mailbox before
this produces a deck you'd trust in front of execs.**

## Setup

Requires Python 3.11+ and, for the current mailbox backend, Windows with
Outlook installed and signed in to an account with the shared mailbox added.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env`:
- Jira base URL, email, and an [API token](https://id.atlassian.com/manage-profile/security/api-tokens)
- The 3-4 Jira custom field IDs (see OPEN_QUESTIONS.md #2-3) — not guessable, must be looked up
- The shared mailbox's display name as it appears in Outlook's folder pane

Then fill in the real data files (examples provided, gitignored so real data
never gets committed):

```bash
copy config\department_mapping.example.csv config\department_mapping.csv
```
(edit it to match your real departments)

## Running it

```bash
python -m it_intake_reporting.cli --week-ending 2026-05-11
```

Defaults `--week-ending` to the most recent Monday if omitted. Writes
`output/IT_Intake_Weekly_Exec_Summary_<date>.pptx` and appends a row to
`config/rolling_history.xlsx`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

`tests/test_pipeline_smoke.py` runs the full pipeline against fake mailbox/Jira
clients and synthetic data, and checks the result is a structurally valid
`.pptx` — it doesn't validate that the real parsing assumptions are correct
(see OPEN_QUESTIONS.md), only that everything is wired together correctly.
