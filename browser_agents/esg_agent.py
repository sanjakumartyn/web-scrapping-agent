"""Browser agent that scrapes sustainability/ESG content from company website."""
import asyncio

from layer1_agents.browser_agents.playwright_scraper import scrape_url


ESG_PAGE_TIMEOUT_MS = 4000


async def collect_esg(company_name: str, website: str) -> str:
    """Collect sustainability/ESG content from the company's website.

    Tries common sustainability page URLs and extracts content about
    environmental targets, net-zero commitments, renewable energy, and
    other ESG initiatives. Returns plain text content.

    Errors are caught and an empty string is returned on failure.
    """
    try:
        if not website:
            return ""

        # Try the configured URL first. Some companies use a separate ESG domain.
        direct_content = await scrape_url(website, timeout=ESG_PAGE_TIMEOUT_MS)
        if direct_content and len(direct_content) > 100:
            return direct_content

        paths = [
            "/sustainability",
            "/esg",
            "/csr",
            "/corporate-social-responsibility",
        ]

        results = await asyncio.gather(
            *[scrape_url(website.rstrip("/") + path, timeout=ESG_PAGE_TIMEOUT_MS) for path in paths],
            return_exceptions=True,
        )
        for content in results:
            if isinstance(content, Exception):
                continue
            if content and len(content) > 100:
                return str(content)
        return direct_content or ""
    except Exception as e:
        print(f"esg_agent error: {e}")
        return ""
