"""Weekly entrypoint: `python -m it_intake_reporting.cli [--week-ending YYYY-MM-DD]`.

Defaults --week-ending to the most recent Monday (matching the template's
"Week Ending ... (Mon)" convention).
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

from .config import load_settings
from .jira_client import JiraClient
from .mailbox.outlook_com import OutlookComMailboxClient
from .pipeline import run_weekly_pipeline


def _most_recent_monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--week-ending",
        type=date.fromisoformat,
        default=None,
        help="ISO date (YYYY-MM-DD). Defaults to the most recent Monday.",
    )
    args = parser.parse_args()

    week_ending = args.week_ending or _most_recent_monday(date.today())

    settings = load_settings()
    mailbox_client = OutlookComMailboxClient(settings.outlook_shared_mailbox_name)
    jira_client = JiraClient(settings.jira_base_url, settings.jira_email, settings.jira_api_token)

    output_path = run_weekly_pipeline(settings, week_ending, mailbox_client, jira_client)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
