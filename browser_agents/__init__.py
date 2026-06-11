"""Browser agents package."""

from .news_agent import collect_news
from .report_agent import collect_report
from .hiring_agent import collect_hiring
from .esg_agent import collect_esg

__all__ = [
    "collect_news",
    "collect_report",
    "collect_hiring",   
    "collect_esg",
]
