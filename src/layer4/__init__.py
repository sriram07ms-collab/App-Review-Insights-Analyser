"""Layer 4: email drafting and sending utilities."""

from .config import Layer4Config
from .email_pipeline import WeeklyEmailPipeline

__all__ = ["Layer4Config", "WeeklyEmailPipeline"]

