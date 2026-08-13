"""Microsoft Graph backend — not implemented yet.

Swapping from Outlook COM to this is the answer to "how hard is it to move
to Graph later": implement `iter_messages` below with the same signature as
`OutlookComMailboxClient.iter_messages` (see mailbox/base.py), then change
the one line in pipeline.py that constructs the mailbox client. Nothing in
transition_parser.py or the pipeline needs to change.

To make this real you'll need, from your Azure AD admin:
  - An app registration with `Mail.Read` (application permission, since this
    runs unattended against a shared mailbox — not `Mail.Read` delegated).
  - Admin consent granted for that permission.
  - Client id / tenant id / client secret, and the shared mailbox's UPN.

Then, roughly:
  1. Acquire a token via MSAL (`msal.ConfidentialClientApplication`,
     `.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])`).
  2. `GET /users/{shared-mailbox-upn}/mailFolders/{folder-id}/messages`
     (paginated via `@odata.nextLink`), filtered with
     `$filter=receivedDateTime ge {since_iso}` when `since` is given.
  3. Map each Graph message resource to `RawMessage(subject=m["subject"],
     body=m["body"]["content"], received_at=..., sender=...)`. Note Graph's
     default body content-type is HTML, not plain text — either request
     `$select=...&Prefer: outlook.body-content-type="text"` or strip HTML
     before handing it to transition_parser.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator

from .base import RawMessage


class GraphMailboxClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, mailbox_upn: str):
        raise NotImplementedError(
            "Graph backend is a stub — see this module's docstring for what's needed "
            "to implement it."
        )

    def iter_messages(
        self, folder_path: str, since: datetime | None = None
    ) -> Iterator[RawMessage]:
        raise NotImplementedError
