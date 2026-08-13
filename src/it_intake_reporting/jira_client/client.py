"""Thin wrapper around the Jira Cloud REST API (v3).

Uses the token-paginated `/rest/api/3/search/jql` endpoint (the old
startAt-paginated `/rest/api/3/search` was retired by Atlassian) and basic
auth with an email + API token, per
https://developer.atlassian.com/cloud/jira/platform/rest/v3/.
"""
from __future__ import annotations

from collections.abc import Iterator

import requests


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.auth = (email, api_token)
        self._session.headers.update({"Accept": "application/json"})

    def search_issues(
        self,
        jql: str,
        fields: list[str] | None = None,
        page_size: int = 100,
    ) -> Iterator[dict]:
        """Yield every issue (as raw Jira JSON) matching the given JQL."""
        url = f"{self.base_url}/rest/api/3/search/jql"
        next_page_token: str | None = None

        while True:
            body: dict = {"jql": jql, "maxResults": page_size}
            if fields is not None:
                body["fields"] = fields
            if next_page_token:
                body["nextPageToken"] = next_page_token

            resp = self._session.post(url, json=body, timeout=self.timeout)
            resp.raise_for_status()
            payload = resp.json()

            yield from payload.get("issues", [])

            if payload.get("isLast", True):
                break
            next_page_token = payload.get("nextPageToken")
            if not next_page_token:
                break

    def get_issue(self, key: str, fields: list[str] | None = None) -> dict:
        url = f"{self.base_url}/rest/api/3/issue/{key}"
        params = {"fields": ",".join(fields)} if fields else None
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
