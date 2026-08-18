# Architecture

```
mailbox (Outlook COM)  ─┐
                         ├─> panels/*.py (pure computation) ─> deck/template_filler.py ─> weekly .pptx
jira_client (REST API) ─┤                ^
                         │                │
mapping (dept -> fn)  ───┘         history/rolling_workbook.py
                                    (persists this week's row,
                                     feeds next week's deltas
                                     and the trend panels)
```

`pipeline.py` is the only module that wires these together — everything else
is independently testable. `cli.py` is the thin entrypoint that constructs
the real backends (Outlook COM, live Jira) and calls `pipeline.run_weekly_pipeline`.

## Module map

| Module | Responsibility |
|---|---|
| `config.py` | Loads `.env` into a typed `Settings` object. Nothing else touches environment variables. |
| `models.py` | Shared dataclasses (`TransitionEvent`, `JiraRequest`, `WeeklySnapshot`) passed between layers. |
| `vocabulary.py` | Domain constants (review teams, sub-task statuses, aging buckets) — see docs/OPEN_QUESTIONS.md #4. |
| `mailbox/` | `base.py` defines the `MailboxClient` interface; `outlook_com.py` is the real (Windows/Outlook) implementation; `graph.py` is a documented stub for the future Graph backend; `transition_parser.py` turns one raw email into a `TransitionEvent`. |
| `jira_client/` | Thin wrapper over the Jira Cloud REST API v3 (`/rest/api/3/search/jql`, token-paginated). |
| `mapping/` | Loads the department -> function CSV for panel 5. |
| `history/` | `RollingHistoryWorkbook` — one Excel row per week, backing the trend panels (2, 4) and headline deltas beyond what a single run's live data covers. `SubtaskTransitionStore` — our own persisted record of each open sub-task's latest known transition, so panels 3/7 don't lose a sub-task that had zero activity in one run's mailbox fetch window. See docs/OPEN_QUESTIONS.md #1a. |
| `panels/` | One module per template panel (see docs/DATA_SOURCES.md), each a pure function: typed inputs in, a typed result out. No I/O. |
| `deck/template_filler.py` | Maps logical field names to the template's actual shape names and writes values/chart data into a copy of the template. |
| `pipeline.py` | Orchestrates: fetch -> compute -> persist history -> fill deck. |
| `cli.py` | `python -m it_intake_reporting.cli [--week-ending YYYY-MM-DD]`. |

## Why a rolling history workbook, not just live queries

Panel 2 (12-week throughput trend) and panel 4 (12-month cycle-time trend)
need history well beyond what Outlook's mailbox retention or a single Jira
query window can reliably provide every week. So every run appends (or
overwrites, if re-run for the same week) one row to
`config/rolling_history.xlsx`, and the trend panels read the last N rows back
out rather than re-deriving history from source each time. This also backs
the headline stats' week-over-week deltas.

## Adding a new panel or changing a computation

1. Add/edit the pure function in `panels/`. It should take plain data in
   (lists of `TransitionEvent`/`JiraRequest`, or primitives) and return a
   small dataclass — no reaching into `Settings` or clients directly.
2. Wire it into `pipeline.py`: call the function, feed its result into
   `_build_deck_values`.
3. If it needs a new template field, add the shape's name to
   `deck/template_filler.py::FIELD_SHAPES` (find it by opening the template
   with `python-pptx` and walking `slide.shapes` — see the pptx skill).
4. Extend `tests/test_pipeline_smoke.py`'s fixtures to exercise it.
