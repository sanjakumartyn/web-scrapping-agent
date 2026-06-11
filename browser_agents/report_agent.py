"""Browser agent that finds and extracts investor reports from investor relations pages."""
from layer1_agents.browser_agents.playwright_scraper import scrape_url


async def collect_report(company_name: str, investor_url: str) -> str:
    """Collect text from investor relations pages and reports.

    Scrapes the investor_url for financial documents, annual reports, and
    sustainability information. Returns plain text content.

    Errors are caught and an empty string is returned on failure.
    """
    try:
        return await scrape_url(investor_url, timeout=30000)
    except Exception as e:
        print(f"report_agent error: {e}")
        return ""
