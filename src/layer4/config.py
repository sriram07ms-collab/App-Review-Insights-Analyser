"""Configuration helpers for Layer 4 (email drafting + sending)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_or_default(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Layer4Config:
    """Runtime configuration for email drafting and delivery."""

    product_name: str = field(default_factory=lambda: _env_or_default("PRODUCT_NAME", "Groww App"))
    email_recipient: str = field(default_factory=lambda: _env_or_default("EMAIL_RECIPIENT", "me@example.com"))
    email_sender: str = field(default_factory=lambda: _env_or_default("EMAIL_SENDER", "noreply@example.com"))
    transport: str = field(default_factory=lambda: _env_or_default("EMAIL_TRANSPORT", "smtp"))  # smtp|gmail
    log_path: Path = field(default_factory=lambda: Path(os.getenv("LAYER4_EMAIL_LOG", "data/processed/email_logs.csv")))
    pulses_dir: Path = field(default_factory=lambda: Path(os.getenv("LAYER4_PULSES_DIR", os.getenv("LAYER3_OUTPUT_DIR", "data/processed/weekly_pulse"))))
    dry_run: bool = field(default_factory=lambda: _env_bool("EMAIL_DRY_RUN", True))

    # LLM configuration
    email_model_name: str = field(default_factory=lambda: _env_or_default("LAYER4_EMAIL_MODEL_NAME", _env_or_default("GEMINI_MODEL_NAME", "models/gemini-2.5-flash")))
    subject_template: str = field(default_factory=lambda: os.getenv("EMAIL_SUBJECT_TEMPLATE", "Weekly Product Pulse – {product} ({week_start}–{week_end})"))

    # SMTP settings
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "smtp.gmail.com"))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    smtp_use_tls: bool = field(default_factory=lambda: _env_bool("SMTP_USE_TLS", True))

    # Gmail API settings (if using Gmail transport)
    gmail_user: str = field(default_factory=lambda: os.getenv("GMAIL_USER", ""))
    gmail_credentials_path: Path = field(default_factory=lambda: Path(os.getenv("GMAIL_CREDENTIALS_PATH", "config/gmail_credentials.json")))
    gmail_token_path: Path = field(default_factory=lambda: Path(os.getenv("GMAIL_TOKEN_PATH", "config/gmail_token.json")))

    def __post_init__(self) -> None:
        self.gmail_credentials_path = self._materialize_secret(
            inline_value=os.getenv("GMAIL_CREDENTIALS_JSON"),
            path=self.gmail_credentials_path,
            default_filename="gmail_credentials.json",
        )
        self.gmail_token_path = self._materialize_secret(
            inline_value=os.getenv("GMAIL_TOKEN_JSON"),
            path=self.gmail_token_path,
            default_filename="gmail_token.json",
        )

    @staticmethod
    def _materialize_secret(inline_value: str | None, path: Path, default_filename: str) -> Path:
        """
        If an inline JSON secret is provided (e.g., via GitHub Actions secrets),
        write it to disk so Google client libraries can read it from a file path.
        """
        if inline_value:
            target_dir = path.parent if path else Path("config")
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / (path.name or default_filename)
            target_path.write_text(inline_value, encoding="utf-8")
            return target_path
        return path

