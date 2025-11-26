"""Email sending utilities for Layer 4."""

from __future__ import annotations

import csv
import logging
import smtplib
import base64
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import Layer4Config
from .email_models import EmailDraft, EmailLogEntry

LOGGER = logging.getLogger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class EmailSender:
    """Sends email via SMTP or Gmail API."""

    def __init__(self, config: Layer4Config) -> None:
        self.config = config
        self._gmail_service = None

    def send(self, draft: EmailDraft) -> EmailLogEntry:
        timestamp = datetime.now(timezone.utc)
        if self.config.dry_run:
            LOGGER.info("Dry run: would send email to %s with subject '%s'", draft.recipient, draft.subject)
            status = "dry_run"
        else:
            if self.config.transport.lower() == "gmail":
                self._send_via_gmail(draft)
            else:
                self._send_via_smtp(draft)
            status = "sent"

        entry = EmailLogEntry(
            timestamp=timestamp,
            week_start=draft.week_start,
            week_end=draft.week_end,
            recipient=draft.recipient,
            subject=draft.subject,
            status=status,
            transport=self.config.transport,
        )
        self._append_log(entry)
        return entry

    def _send_via_smtp(self, draft: EmailDraft) -> None:
        msg = EmailMessage()
        msg["From"] = self.config.email_sender
        msg["To"] = draft.recipient
        msg["Subject"] = draft.subject
        msg.set_content(draft.body)

        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
            if self.config.smtp_use_tls:
                server.starttls()
            if self.config.smtp_user and self.config.smtp_password:
                server.login(self.config.smtp_user, self.config.smtp_password)
            server.send_message(msg)
        LOGGER.info("Email sent to %s via SMTP.", draft.recipient)

    def _send_via_gmail(self, draft: EmailDraft) -> None:
        service = self._get_gmail_service()
        if service is None:
            raise RuntimeError("Unable to initialize Gmail service.")

        message = EmailMessage()
        message["From"] = self.config.email_sender or self.config.gmail_user
        message["To"] = draft.recipient
        message["Subject"] = draft.subject
        message.set_content(draft.body)

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        service.users().messages().send(userId="me", body={"raw": encoded_message}).execute()
        LOGGER.info("Email sent to %s via Gmail API.", draft.recipient)

    def _get_gmail_service(self):
        if self._gmail_service is not None:
            return self._gmail_service

        creds = None
        token_path = self.config.gmail_token_path
        credentials_path = self.config.gmail_credentials_path

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), GMAIL_SCOPES)
                creds = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with token_path.open("w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())

        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        self._gmail_service = service
        return service

    def _append_log(self, entry: EmailLogEntry) -> None:
        log_path: Path = self.config.log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not log_path.exists()
        with log_path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if is_new:
                writer.writerow(["timestamp", "week_start", "week_end", "recipient", "subject", "status", "transport"])
            writer.writerow(
                [
                    entry.timestamp.isoformat(),
                    entry.week_start,
                    entry.week_end,
                    entry.recipient,
                    entry.subject,
                    entry.status,
                    entry.transport,
                ]
            )

