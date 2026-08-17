"""Orchestrates one weekly run: pull this week's data, compute every panel,
persist the rolling history row, and fill the deck template.

See docs/DATA_SOURCES.md for which data source backs which panel, and
docs/OPEN_QUESTIONS.md for what's still unresolved (Jira custom field ids,
the transition-email format, the working-hours source).
"""
from __future__ import annotations

import warnings
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .config import Settings
from .deck.template_filler import ChartUpdate, DeckValues, fill_deck
from .history.rolling_workbook import RollingHistoryWorkbook
from .jira_client import JiraClient
from .mailbox.base import MailboxClient
from .mailbox.transition_parser import parse_transition_email
from .mapping import DepartmentMapping
from .models import JiraRequest, TransitionEvent, WeeklySnapshot
from .panels.headline import compute_headline_stats
from .panels.panel1_backlog import compute_backlog
from .panels.panel2_throughput import compute_throughput_trend
from .panels.panel3_review_effort import compute_where_time_goes, compute_working_hours
from .panels.panel4_cycle_time import compute_cycle_time_trend, median_cycle_time_days
from .panels.panel5_demand import compute_demand_by_function
from .panels.panel6_aging import compute_aging
from .panels.panel7_stalled import compute_stalled
from .vocabulary import REVIEW_TEAMS, SUBTASK_STATUSES

JIRA_ISSUE_FIELDS = ["status", "statuscategory", "created", "updated", "components"]

HISTORY_WEEKS_TO_LOAD = 53  # ~12 months, for the monthly cycle-time rollup


def run_weekly_pipeline(
    settings: Settings,
    week_ending: date,
    mailbox_client: MailboxClient,
    jira_client: JiraClient,
    run_datetime: datetime | None = None,
) -> Path:
    run_datetime = run_datetime or datetime.now()

    mapping = DepartmentMapping.from_csv(settings.department_mapping_csv)
    history_wb = RollingHistoryWorkbook(settings.rolling_history_xlsx)
    history = history_wb.read_recent_weeks(HISTORY_WEEKS_TO_LOAD)
    previous_week = history[-1] if history else None

    events = _fetch_transition_events(settings, mailbox_client, week_ending)
    parent_events = [e for e in events if e.is_parent_request]
    subtask_events = [e for e in events if not e.is_parent_request]

    jira_fields = [
        settings.jira_field_department,
        settings.jira_field_review_team,
        settings.jira_field_exec_critical,
        *JIRA_ISSUE_FIELDS,
    ]
    active_requests = [
        _jira_issue_to_request(issue, settings, mapping)
        for issue in jira_client.search_issues(settings.jira_jql_active_requests, fields=jira_fields)
    ]

    # --- Panel 1: backlog bridge ---
    opening_balance = previous_week.open_requests_active if previous_week else len(active_requests)
    backlog = compute_backlog(parent_events, opening_balance)
    if not backlog.matches_jira(len(active_requests)):
        warnings.warn(
            f"Panel 1 closing balance ({backlog.closing_balance}) does not match the "
            f"Jira dashboard's active count ({len(active_requests)}). Deck numbers may "
            "be wrong — check for transition emails Outlook didn't deliver, or JQL drift. "
            "See docs/DATA_SOURCES.md panel 1.",
            stacklevel=2,
        )

    # --- Panel 2: throughput trend ---
    this_week_opened = backlog.newly_opened + backlog.re_opened
    this_week_closed = backlog.completed
    throughput_trend = compute_throughput_trend(history, week_ending, this_week_opened, this_week_closed)

    # --- Panel 3: where time goes (real) + working hours (needs a source — see OPEN_QUESTIONS.md) ---
    latest_subtask_transition = _latest_transition_per_ticket(subtask_events)
    where_time_goes = compute_where_time_goes(latest_subtask_transition, as_of=run_datetime)
    if settings.jira_field_hours:
        hours_by_team_and_status = _hours_by_team_and_status(
            subtask_events, jira_client, settings.jira_field_hours
        )
    else:
        warnings.warn(
            "JIRA_FIELD_HOURS is not set — panel 3's Working Hours table will be all "
            "zeros. See docs/OPEN_QUESTIONS.md.",
            stacklevel=2,
        )
        hours_by_team_and_status = {}
    working_hours = compute_working_hours(hours_by_team_and_status)

    # --- Panel 4: cycle time trend ---
    completed_pairs = _completed_cycle_time_pairs(parent_events, jira_client)
    this_month_median = median_cycle_time_days(completed_pairs)
    cycle_time_trend = compute_cycle_time_trend(
        history, week_ending.strftime("%Y-%m"), this_month_median
    )

    # --- Panels 5-6 ---
    demand_by_function = compute_demand_by_function(active_requests, mapping)
    aging = compute_aging(active_requests, as_of=run_datetime)

    # --- Panel 7: stalled reviews — sub-task level (see docs/OPEN_QUESTIONS.md) ---
    stalled_by_team = compute_stalled(latest_subtask_transition)

    # --- Headline stats ---
    exec_critical_open = sum(1 for r in active_requests if r.is_exec_critical)
    headline = compute_headline_stats(
        open_requests_active=backlog.closing_balance,
        resolved_this_week=backlog.completed,
        aging_90_plus=aging.total_over_90_days,
        exec_critical_open=exec_critical_open,
        previous_week=previous_week,
    )

    # --- Persist this week's row for future trend/delta computations ---
    history_wb.append_week(
        WeeklySnapshot(
            week_ending=week_ending,
            opened=this_week_opened,
            closed=this_week_closed,
            median_cycle_time_days=this_month_median,
            working_hours_by_team=working_hours.working_hours_by_team,
            open_requests_active=backlog.closing_balance,
            resolved_this_week=backlog.completed,
            aging_90_plus=aging.total_over_90_days,
            exec_critical_open=exec_critical_open,
        )
    )

    # --- Fill the deck ---
    deck_values = _build_deck_values(
        week_ending=week_ending,
        run_datetime=run_datetime,
        headline=headline,
        backlog=backlog,
        throughput_trend=throughput_trend,
        where_time_goes=where_time_goes,
        working_hours=working_hours,
        cycle_time_trend=cycle_time_trend,
        this_month_median=this_month_median,
        demand_by_function=demand_by_function,
        aging=aging,
        stalled_by_team=stalled_by_team,
    )
    output_path = settings.deck_output_dir / f"IT_Intake_Weekly_Exec_Summary_{week_ending.isoformat()}.pptx"
    fill_deck(settings.deck_template_pptx, output_path, deck_values)
    return output_path


def _fetch_transition_events(
    settings: Settings, mailbox_client: MailboxClient, week_ending: date
) -> list[TransitionEvent]:
    since = datetime.combine(week_ending, time.min) - timedelta(days=7)
    events = []
    for message in mailbox_client.iter_messages(settings.outlook_transitions_folder, since=since):
        try:
            events.extend(parse_transition_email(message))
        except ValueError as exc:
            warnings.warn(f"Skipping unparseable email {message.subject!r}: {exc}", stacklevel=2)
    return events


def _latest_transition_per_ticket(events: list[TransitionEvent]) -> list[TransitionEvent]:
    latest: dict[str, TransitionEvent] = {}
    for event in events:
        current = latest.get(event.ticket_key)
        if current is None or event.changed_at > current.changed_at:
            latest[event.ticket_key] = event
    return list(latest.values())


def _completed_cycle_time_pairs(
    parent_events: list[TransitionEvent], jira_client: JiraClient
) -> list[tuple[date, date]]:
    pairs = []
    for event in parent_events:
        if event.to_status != "Completed":
            continue
        issue = jira_client.get_issue(event.ticket_key, fields=["created"])
        created = _parse_jira_datetime(issue["fields"]["created"])
        pairs.append((created.date(), event.changed_at.date()))
    return pairs


def _hours_by_team_and_status(
    subtask_events: list[TransitionEvent], jira_client: JiraClient, hours_field: str
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    latest = _latest_transition_per_ticket(subtask_events)
    for event in latest:
        if event.review_team is None:
            continue
        issue = jira_client.get_issue(event.ticket_key, fields=[hours_field])
        hours = issue["fields"].get(hours_field) or 0.0
        team_bucket = result.setdefault(event.review_team, {})
        team_bucket[event.to_status] = team_bucket.get(event.to_status, 0.0) + float(hours)
    return result


def _jira_issue_to_request(issue: dict, settings: Settings, mapping: DepartmentMapping) -> JiraRequest:
    fields = issue["fields"]
    department_raw = fields.get(settings.jira_field_department) or ""
    department = department_raw.get("value") if isinstance(department_raw, dict) else department_raw
    review_team_raw = fields.get(settings.jira_field_review_team)
    review_team = review_team_raw.get("value") if isinstance(review_team_raw, dict) else review_team_raw

    return JiraRequest(
        key=issue["key"],
        summary=fields.get("summary", ""),
        status=fields["status"]["name"],
        status_category=fields["status"]["statusCategory"]["name"],
        department=department or "",
        review_team=review_team,
        created=_parse_jira_datetime(fields["created"]),
        updated=_parse_jira_datetime(fields["updated"]),
        is_exec_critical=bool(fields.get(settings.jira_field_exec_critical)),
        raw_fields=fields,
    )


def _parse_jira_datetime(value: str) -> datetime:
    # Jira returns e.g. "2026-05-01T10:15:00.000-0700".
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")


def _build_deck_values(
    *,
    week_ending: date,
    run_datetime: datetime,
    headline,
    backlog,
    throughput_trend,
    where_time_goes,
    working_hours,
    cycle_time_trend,
    this_month_median: float,
    demand_by_function: dict[str, int],
    aging,
    stalled_by_team: dict[str, int],
) -> DeckValues:
    def delta_text(delta: int, suffix: str = "vs last week") -> str:
        arrow = "▲" if delta > 0 else "▼" if delta < 0 else "–"
        return f"{arrow} {abs(delta)} {suffix}"

    top_stalled_teams = sorted(stalled_by_team.items(), key=lambda kv: kv[1], reverse=True)
    top_stalled_teams += [("—", 0)] * (3 - len(top_stalled_teams))  # pad if fewer than 3 teams

    text_fields = {
        "week_ending": f"Week Ending   {week_ending.strftime('%B %d, %Y (%a)')}",
        "data_as_of": f"Data as of {run_datetime.strftime('%B %d, %Y %I:%M %p')}",
        "headline_open_active": str(headline.open_requests_active),
        "headline_open_active_delta": delta_text(headline.open_requests_delta),
        "headline_resolved": str(headline.resolved_this_week),
        "headline_resolved_delta": delta_text(headline.resolved_delta),
        "headline_aging_90": str(headline.aging_90_plus),
        "headline_aging_90_delta": delta_text(headline.aging_delta),
        "headline_exec_critical": str(headline.exec_critical_open),
        "headline_exec_critical_delta": delta_text(headline.exec_critical_delta),
        "p1_opening_balance": str(backlog.opening_balance),
        "p1_newly_opened": f"+ {backlog.newly_opened}",
        "p1_completed": f"− {backlog.completed}",
        "p1_not_approved": f"− {backlog.not_approved}",
        "p1_cancelled": f"− {backlog.cancelled}",
        "p1_on_hold": f"− {backlog.on_hold}",
        "p1_re_opened": f"+ {backlog.re_opened}",
        "p2_this_week_opened": str(backlog.newly_opened + backlog.re_opened),
        "p2_this_week_closed": str(backlog.completed),
        # These are the "Working Hours" (Not Started + Review In Progress)
        # subset per team, per the template's own footnote — not each
        # team's total hours across every status.
        "p3_hours_CyberArch": f"{working_hours.working_hours_by_team.get('CyberArch', 0):.0f} hrs",
        "p3_hours_TPRM": f"{working_hours.working_hours_by_team.get('TPRM', 0):.0f} hrs",
        "p3_hours_Legal": f"{working_hours.working_hours_by_team.get('Legal', 0):.0f} hrs",
        "p3_hours_IAM": f"{working_hours.working_hours_by_team.get('IAM', 0):.0f} hrs",
        "p3_hours_AI": f"{working_hours.working_hours_by_team.get('AI', 0):.0f} hrs",
        "p3_hours_Sub-ARB": f"{working_hours.working_hours_by_team.get('Sub-ARB', 0):.0f} hrs",
        "p3_hours_total": f"{working_hours.total_working_hours:.0f} hrs",
        "p4_median_days": str(round(this_month_median)),
        "p4_delta": delta_text(
            round(this_month_median - cycle_time_trend[-2].median_days) if len(cycle_time_trend) > 1 else 0,
            suffix="vs",
        ),
        "p6_bucket_0_30": str(aging.total_by_bucket.get("0–30 days", 0)),
        "p6_bucket_31_60": str(aging.total_by_bucket.get("31–60 days", 0)),
        "p6_bucket_61_90": str(aging.total_by_bucket.get("61–90 days", 0)),
        "p6_bucket_90_plus": str(aging.total_over_90_days),
        "p7_stalled_total": str(sum(stalled_by_team.values())),
        "p7_top_team_1_name": top_stalled_teams[0][0],
        "p7_top_team_1_count": str(top_stalled_teams[0][1]),
        "p7_top_team_2_name": top_stalled_teams[1][0],
        "p7_top_team_2_count": str(top_stalled_teams[1][1]),
        "p7_top_team_3_name": top_stalled_teams[2][0],
        "p7_top_team_3_count": str(top_stalled_teams[2][1]),
    }

    charts = {
        "Chart 0": ChartUpdate(
            categories=[p.week_ending.isoformat() for p in throughput_trend],
            series={
                "Opened": [p.opened for p in throughput_trend],
                "Closed": [p.closed for p in throughput_trend],
            },
        ),
        "Chart 1": ChartUpdate(
            categories=REVIEW_TEAMS,
            series={
                status: [
                    where_time_goes.median_days.get(team, {}).get(status, 0.0)
                    for team in REVIEW_TEAMS
                ]
                for status in SUBTASK_STATUSES
            },
        ),
        "Chart 2": ChartUpdate(
            categories=[p.month for p in cycle_time_trend],
            series={"Median days": [p.median_days for p in cycle_time_trend]},
        ),
        "Chart 3": ChartUpdate(
            categories=list(demand_by_function.keys()),
            series={"Requests": list(demand_by_function.values())},
        ),
    }

    return DeckValues(
        text_fields=text_fields,
        closing_balance_value=str(backlog.closing_balance),
        closing_balance_delta=f"  {'▲' if headline.open_requests_delta >= 0 else '▼'} {abs(headline.open_requests_delta)}",
        charts=charts,
    )
