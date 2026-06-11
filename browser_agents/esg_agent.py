"""Browser agent that scrapes sustainability/ESG content from company website."""
from layer1_agents.browser_agents.playwright_scraper import scrape_url


async def collect_esg(company_name: str, website: str) -> str:
    """Collect sustainability/ESG content from the company's website.

    Tries common sustainability page URLs and extracts content about
    environmental targets, net-zero commitments, renewable energy, and
    other ESG initiatives. Returns plain text content.

    Errors are caught and an empty string is returned on failure.
    """
    try:
        # Try common ESG/sustainability page paths
        paths = [
            "/sustainability",
            "/esg",
            "/environment",
            "/corporate-social-responsibility",
            "/csr",
            "/green",
        ]

        for path in paths:
            url = website.rstrip("/") + path
            try:
                content = await scrape_url(url, timeout=20000)
                if content and len(content) > 100:  # Only return if substantial
                    return content
            except:
                continue

        # Fallback: scrape homepage
        return await scrape_url(website, timeout=20000)
    except Exception as e:
        print(f"esg_agent error: {e}")
        return ""
