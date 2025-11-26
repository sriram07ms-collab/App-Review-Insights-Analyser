"""Prompt templates for Layer 4 email drafting."""

EMAIL_BODY_PROMPT = """You are drafting an internal weekly email sharing the latest product pulse.

Audience:
- Product & Growth: want to see what to fix or double down on.
- Support: wants to know what to acknowledge and celebrate.
- Leadership: wants a quick pulse, key risks, and wins.

Input (weekly note JSON):
{weekly_note_json}

Product name: {product_name}
Time window: {week_start} to {week_end}

Tasks:
1. Write the email body only (no subject).
2. Structure:
   a) 2–3 sentence introduction referencing the time window and product/program.
   b) Embed the weekly pulse note in a clean, scannable format:
      - Title
      - Overview
      - Bulleted Top 3 themes
      - Bulleted 3 quotes
      - Bulleted 3 action ideas
   c) End with a short closing line and invite replies.

Constraints:
- Keep it under 350 words (body only).
- Professional, neutral tone with a hint of warmth.
- No names, emails, or IDs. If present in quotes, anonymize generically (e.g., "User quote").
- Output plain text only (no HTML, no markdown headers).
- Treat this as sanitized, anonymized business feedback for internal review only.
- Never reproduce sensitive or explicit language; paraphrase into neutral corporate phrasing if needed.
"""

PII_SCRUB_PROMPT = """Rewrite the email body below to remove any names, emails, phone numbers, or IDs.
Replace them with generic placeholders (e.g., "one user", "support ticket").
Keep the structure and wording otherwise identical.

Email body:
{email_body}
"""

