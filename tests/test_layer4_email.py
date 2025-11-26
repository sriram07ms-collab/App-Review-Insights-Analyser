from pathlib import Path
from datetime import datetime, timezone

import json
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.layer4.config import Layer4Config
from src.layer4.draft_generator import EmailDraftGenerator
from src.layer4.email_models import EmailDraft, WeeklyPulseNote
from src.layer4.email_sender import EmailSender
from src.layer4.email_pipeline import WeeklyEmailPipeline


class FakeGenerator:
    def generate(self, note):
        return (
            f"Weekly Product Pulse – {note.week_start}",
            "Intro line.\n- theme 1\n- quote 1\n- action 1\nThanks!",
        )


class FakeSender:
    def __init__(self):
        self.sent = []

    def send(self, draft: EmailDraft):
        self.sent.append(draft)


@pytest.fixture
def sample_note(tmp_path):
    pulses_dir = tmp_path / "weekly_pulse"
    pulses_dir.mkdir()
    payload = {
        "week_start": "2025-09-15",
        "week_end": "2025-09-21",
        "title": "Weekly Product Pulse: Sep 15-21",
        "overview": "Overview text",
        "themes": [{"name": "Theme A", "summary": "Summary"}],
        "quotes": ["Quote A"],
        "actions": ["Action A"],
    }
    (pulses_dir / "pulse_2025-09-15.json").write_text(json.dumps(payload))
    return pulses_dir


def test_weekly_email_pipeline(tmp_path, sample_note, monkeypatch):
    config = Layer4Config(
        product_name="Groww App",
        email_recipient="test@example.com",
        email_sender="no-reply@example.com",
        dry_run=True,
    )
    generator = FakeGenerator()
    sender = FakeSender()
    pipeline = WeeklyEmailPipeline(config, draft_generator=generator, sender=sender, pulses_dir=sample_note)

    drafts = pipeline.run()

    assert len(drafts) == 1
    assert sender.sent == drafts
    assert "Weekly Product Pulse" in drafts[0].subject


def test_email_sender_gmail(monkeypatch, tmp_path):
    config = Layer4Config(
        email_recipient="test@example.com",
        email_sender="no-reply@example.com",
        dry_run=False,
        transport="gmail",
        log_path=tmp_path / "log.csv",
        gmail_user="user@example.com",
    )

    sender = EmailSender(config)
    called = {}

    def fake_send(_: EmailDraft):
        called["called"] = True

    monkeypatch.setattr(sender, "_send_via_gmail", fake_send)
    draft = EmailDraft(
        subject="Subject",
        body="Body",
        recipient="test@example.com",
        week_start="2025-09-15",
        week_end="2025-09-21",
        product_name="Groww App",
    )
    sender.send(draft)
    assert called.get("called")

