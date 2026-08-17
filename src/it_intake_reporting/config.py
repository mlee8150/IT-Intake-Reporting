"""Central settings, loaded from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    jira_base_url: str
    jira_email: str
    jira_api_token: str
    jira_jql_active_requests: str
    jira_field_department: str
    jira_field_exec_critical: str

    outlook_shared_mailbox_name: str
    outlook_transitions_folder: str

    department_mapping_csv: Path
    rolling_history_xlsx: Path
    deck_template_pptx: Path
    deck_output_dir: Path


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(
            f"Missing required setting {name!r}. Copy .env.example to .env and fill it in."
        )
    return value


def load_settings(env_file: Path | None = None) -> Settings:
    load_dotenv(env_file or REPO_ROOT / ".env")

    return Settings(
        jira_base_url=_require("JIRA_BASE_URL"),
        jira_email=_require("JIRA_EMAIL"),
        jira_api_token=_require("JIRA_API_TOKEN"),
        jira_jql_active_requests=os.environ.get(
            "JIRA_JQL_ACTIVE_REQUESTS",
            'statusCategory != Done AND issuetype = "Parent Request"',
        ),
        # Custom field ids (e.g. "customfield_10050") — Jira Cloud doesn't
        # expose department/exec-critical as standard fields, so these must
        # be looked up per-instance. See docs/OPEN_QUESTIONS.md. (Review team
        # is not a Jira field — it's derived from the sub-task's own name.)
        jira_field_department=_require("JIRA_FIELD_DEPARTMENT"),
        jira_field_exec_critical=_require("JIRA_FIELD_EXEC_CRITICAL"),
        outlook_shared_mailbox_name=_require("OUTLOOK_SHARED_MAILBOX_NAME"),
        outlook_transitions_folder=os.environ.get("OUTLOOK_TRANSITIONS_FOLDER", "Inbox"),
        department_mapping_csv=REPO_ROOT
        / os.environ.get("DEPARTMENT_MAPPING_CSV", "config/department_mapping.csv"),
        rolling_history_xlsx=REPO_ROOT
        / os.environ.get("ROLLING_HISTORY_XLSX", "config/rolling_history.xlsx"),
        deck_template_pptx=REPO_ROOT
        / os.environ.get(
            "DECK_TEMPLATE_PPTX", "templates/Technology_Intake_Weekly_Exec_Summary.pptx"
        ),
        deck_output_dir=REPO_ROOT / os.environ.get("DECK_OUTPUT_DIR", "output"),
    )
