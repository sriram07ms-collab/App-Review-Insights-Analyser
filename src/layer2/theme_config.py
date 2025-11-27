"""Fixed theme configuration for Layer 2 classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class ThemeDefinition:
    """Definition of a fixed theme for review classification."""

    id: str
    name: str
    description: str


# Fixed set of 5 themes for review classification
FIXED_THEMES: Dict[str, ThemeDefinition] = {
    "glitches": ThemeDefinition(
        id="glitches",
        name="Slow, Glitches",
        description="When placing order in intraday it place order really late and sometimes even after 20 mins order pending and when the place the order already miss on profits. Even today market is open from 15 mins and still can't place new orders really getting in my nerves now.",
    ),
    "ui_ux": ThemeDefinition(
        id="ui_ux",
        name="UI/UX",
        description="Easy and simple user interface but today I need a stock holding statement for a visa application.",
    ),
    "payments_statements": ThemeDefinition(
        id="payments_statements",
        name="Payments/Statements",
        description="Many problems are there in this app.. and you see more profit on your PL, But when you exit it it will less than the first amount and when you see the loss amount on your PL when exit it the loss amount is more than when you see first... if you put a target number the target will hit only the target number cross above not will hit even reach the target",
    ),
    "customer_support": ThemeDefinition(
        id="customer_support",
        name="Customer Support",
        description="Issues related to customer service, support responsiveness, help requests, and communication with support team.",
    ),
    "slow": ThemeDefinition(
        id="slow",
        name="Slow",
        description="App performance issues, slow loading times, laggy interface, delayed responses, and general performance problems.",
    ),
    "fees_financial_concerns": ThemeDefinition(
        id="fees_financial_concerns",
        name="Fees & Financial Concerns",
        description="Complaints about unexpected charges, brokerage fees, balance deductions, or transparency around financial transactions.",
    ),
}

# Default theme for invalid/empty classifications
DEFAULT_THEME_ID = "ui_ux"  # Fallback to UI/UX if classification fails


def get_theme_by_id(theme_id: str) -> ThemeDefinition:
    """Get theme definition by ID, with fallback to default."""
    return FIXED_THEMES.get(theme_id.lower(), FIXED_THEMES[DEFAULT_THEME_ID])


def get_all_theme_ids() -> list[str]:
    """Return list of all valid theme IDs."""
    return list(FIXED_THEMES.keys())


def format_themes_for_prompt() -> str:
    """Format themes for LLM classification prompt."""
    lines = []
    for idx, (theme_id, theme) in enumerate(FIXED_THEMES.items(), start=1):
        lines.append(f"{idx}. {theme.name} ({theme_id}) – {theme.description}")
    return "\n".join(lines)


def get_theme_by_id_or_discovered(
    theme_id: str,
    discovered_themes: list | None = None,
) -> ThemeDefinition:
    """
    Get theme definition, checking discovered themes first, then predefined.
    
    Args:
        theme_id: Theme ID to look up
        discovered_themes: Optional list of DiscoveredTheme objects
        
    Returns:
        ThemeDefinition (from discovered theme or predefined theme)
    """
    if discovered_themes:
        from .theme_discovery import DiscoveredTheme
        
        discovered = next(
            (t for t in discovered_themes if isinstance(t, DiscoveredTheme) and t.theme_id.lower() == theme_id.lower()),
            None
        )
        if discovered:
            # If mapped to predefined, return predefined
            if discovered.mapped_to_predefined:
                return FIXED_THEMES[discovered.mapped_to_predefined]
            # Otherwise, create a dynamic theme definition from discovered theme
            return ThemeDefinition(
                id=discovered.theme_id,
                name=discovered.theme_name,
                description=discovered.description
            )
    
    # Fallback to predefined
    return get_theme_by_id(theme_id)


