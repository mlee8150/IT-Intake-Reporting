"""The mailbox backend interface.

Everything downstream (transition_parser, the pipeline) only depends on
`MailboxClient` and `RawMessage`. That's deliberate: it's the seam for
swapping the Outlook-desktop (COM) backend for Microsoft Graph later without
touching any parsing or pipeline code — implement `GraphMailboxClient` with
the same `iter_messages` signature (see mailbox/graph.py) and change one
constructor call in pipeline.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Protocol


@dataclass(frozen=True)
class RawMessage:
    subject: str
    body: str
    received_at: datetime
    sender: str


class MailboxClient(Protocol):
    def iter_messages(self, folder_path: str, since: datetime | None = None) -> Iterator[RawMessage]:
        """Yield every message in the given folder, optionally filtered to since a timestamp.

        `folder_path` is backend-specific: for Outlook COM it's a
        "/"-separated path under the shared mailbox root (e.g.
        "Inbox/Jira Transitions"); for Graph it would be a folder id or
        well-known name.
        """
        ...
