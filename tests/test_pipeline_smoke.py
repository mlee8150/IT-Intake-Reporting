"""End-to-end smoke test: fake mailbox + fake Jira -> a valid filled deck.

This doesn't validate real-world parsing assumptions (see
docs/OPEN_QUESTIONS.md for those) — it validates that the pieces are wired
together correctly: transition-email parsing -> panel computation -> rolling
history -> deck template filling, using synthetic data shaped like what the
real backends are expected to return.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from it_intake_reporting.config import Settings
from it_intake_reporting.mailbox.base import RawMessage
from it_intake_reporting.pipeline import run_weekly_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeMailboxClient:
    def __init__(self, messages: list[RawMessage]):
        self._messages = messages

    def iter_messages(self, folder_path, since=None):
        return iter(self._messages)


class FakeJiraClient:
    def __init__(self, active_issues: list[dict], issues_by_key: dict[str, dict]):
        self._active_issues = active_issues
        self._issues_by_key = issues_by_key

    def search_issues(self, jql, fields=None, page_size=100):
        return iter(self._active_issues)

    def get_issue(self, key, fields=None):
        return self._issues_by_key[key]


def _settings(tmp_path: Path) -> Settings:
    mapping_csv = tmp_path / "department_mapping.csv"
    mapping_csv.write_text("department,function\nManufacturing,Mfg & Ops\nSales,Revenue\n")
    return Settings(
        jira_base_url="https://example.atlassian.net",
        jira_email="bot@example.com",
        jira_api_token="token",
        jira_jql_active_requests="statusCategory != Done",
        jira_jql_lifetime_requests="issuetype = \"Parent Request\"",
        jira_field_department="customfield_10001",
        jira_field_exec_critical="customfield_10003",
        outlook_shared_mailbox_name="IT Intake Notifications",
        outlook_transitions_folder="Inbox/Jira Transitions",
        department_mapping_csv=mapping_csv,
        rolling_history_xlsx=tmp_path / "rolling_history.xlsx",
        deck_template_pptx=REPO_ROOT / "templates" / "Technology_Intake_Weekly_Exec_Summary.pptx",
        deck_output_dir=tmp_path / "output",
    )


def _msg(subject: str, body: str, received_at: datetime) -> RawMessage:
    return RawMessage(subject=subject, body=body, received_at=received_at, sender="jira@example.com")


def test_full_pipeline_produces_a_valid_deck(tmp_path):
    week_ending = date(2026, 5, 11)  # a Monday
    run_dt = datetime(2026, 5, 11, 11, 0, tzinfo=timezone.utc)

    messages = [
        _msg("[PROJ-201] moved", "Issue Type: Parent Request\nStatus: Not Started", run_dt),
        _msg(
            "[PROJ-202] moved",
            "Issue Type: Parent Request\nStatus: Review In Progress -> Completed",
            run_dt,
        ),
        _msg(
            "[PROJ-203] moved",
            "Issue Type: Parent Request\nStatus: Review In Progress -> On Hold",
            run_dt,
        ),
        _msg(
            "[PROJ-301] moved",
            "Issue Type: Sub-task\nTeam: CyberArch\nStatus: Review In Progress",
            run_dt,
        ),
        _msg(
            "[PROJ-302] moved",
            "Issue Type: Sub-task\nTeam: TPRM\nStatus: Not Started",
            run_dt,
        ),
    ]
    mailbox_client = FakeMailboxClient(messages)

    def issue(key, department, exec_critical, status, status_category, created, updated):
        return {
            "key": key,
            "fields": {
                "summary": f"{key} summary",
                "status": {"name": status, "statusCategory": {"name": status_category}},
                "customfield_10001": department,
                "customfield_10003": exec_critical,
                "created": created,
                "updated": updated,
            },
        }

    active_issues = [
        issue("PROJ-101", "Manufacturing", True, "Review In Progress", "In Progress",
              "2026-01-05T10:00:00.000+0000", "2026-05-01T10:00:00.000+0000"),
        issue("PROJ-102", "Sales", False, "Not Started", "To Do",
              "2026-04-01T10:00:00.000+0000", "2026-05-10T10:00:00.000+0000"),
    ]
    issues_by_key = {
        "PROJ-202": {"fields": {"created": "2026-04-10T09:00:00.000+0000"}},
    }
    jira_client = FakeJiraClient(active_issues, issues_by_key)

    settings = _settings(tmp_path)
    output_path = run_weekly_pipeline(settings, week_ending, mailbox_client, jira_client, run_datetime=run_dt)

    assert output_path.exists()
    assert settings.rolling_history_xlsx.exists()

    from pptx import Presentation

    prs = Presentation(str(output_path))
    assert len(prs.slides) == 1
