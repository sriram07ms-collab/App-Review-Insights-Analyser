"""
Renderers for Layer 3 outputs.
"""

from __future__ import annotations

from typing import List

from .models import WeeklyPulseNote


def render_markdown(note: WeeklyPulseNote) -> str:
    """Produce a Markdown-friendly version of the weekly pulse."""
    lines: List[str] = []
    lines.append(f"# {note.title or 'Weekly Product Pulse'}")
    lines.append(f"_Week: {note.week_start} - {note.week_end}_")
    lines.append("")
    if note.overview:
        lines.append(note.overview)
        lines.append("")
    if note.themes:
        lines.append("## Themes")
        for theme in note.themes:
            name = theme.get("name", "Theme")
            summary = theme.get("summary", "").strip()
            lines.append(f"- **{name}** - {summary}")
        lines.append("")
    if note.quotes:
        lines.append("## Quotes")
        for quote in note.quotes:
            lines.append(f"- \"{quote}\"")
        lines.append("")
    if note.actions:
        lines.append("## Actions")
        for action in note.actions:
            lines.append(f"- {action}")
        lines.append("")
    lines.append(f"_Word count: {note.word_count}_")
    return "\n".join(lines).strip() + "\n"

