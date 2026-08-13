"""Reads mail via the local, signed-in Outlook desktop client (COM automation).

Requires Outlook to be installed, running (or startable), and already signed
in to an account that has the shared mailbox added — this script does not
handle auth itself, Outlook does. Windows-only.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator

from .base import RawMessage

# Outlook's restriction syntax wants US-format datetimes regardless of locale.
_OUTLOOK_DATE_FORMAT = "%m/%d/%Y %H:%M %p"


class OutlookComMailboxClient:
    def __init__(self, shared_mailbox_name: str):
        self.shared_mailbox_name = shared_mailbox_name
        self._namespace = None

    def _get_namespace(self):
        if self._namespace is None:
            import win32com.client  # imported lazily: only needed on Windows w/ Outlook

            outlook = win32com.client.Dispatch("Outlook.Application")
            self._namespace = outlook.GetNamespace("MAPI")
        return self._namespace

    def _resolve_folder(self, folder_path: str):
        namespace = self._get_namespace()
        root = namespace.Folders[self.shared_mailbox_name]
        folder = root
        for part in folder_path.split("/"):
            part = part.strip()
            if not part:
                continue
            folder = folder.Folders[part]
        return folder

    def iter_messages(
        self, folder_path: str, since: datetime | None = None
    ) -> Iterator[RawMessage]:
        folder = self._resolve_folder(folder_path)
        items = folder.Items
        items.Sort("[ReceivedTime]", False)

        if since is not None:
            restriction = f"[ReceivedTime] >= '{since.strftime(_OUTLOOK_DATE_FORMAT)}'"
            items = items.Restrict(restriction)

        for item in items:
            # MailItem.Class == 43 (olMail); skip meeting invites, receipts, etc.
            if getattr(item, "Class", None) != 43:
                continue
            yield RawMessage(
                subject=item.Subject or "",
                body=item.Body or "",
                received_at=item.ReceivedTime,
                sender=_sender_address(item),
            )


def _sender_address(item) -> str:
    try:
        return item.SenderEmailAddress or ""
    except Exception:
        return ""
