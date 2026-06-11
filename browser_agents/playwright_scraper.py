"""Direct Playwright-based web scraping without LLM reasoning."""
import asyncio
from typing import Optional
from playwright.async_api import async_playwright


async def scrape_url(url: str, timeout: int = 30000) -> str:
    """Scrape content from a URL using Playwright.

    Args:
        url: The URL to scrape.
        timeout: Maximum time in milliseconds to wait for navigation.

    Returns:
        Text content from the page, or empty string on failure.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                # Wait for content to load
                await asyncio.sleep(2)
                # Extract all text content
                text = await page.evaluate("() => document.body.innerText")
                return str(text or "")
            finally:
                await browser.close()
    except Exception as e:
        print(f"scrape_url error for {url}: {e}")
        return ""


async def google_news_search(query: str) -> str:
    """Search Google News and extract headlines/snippets.

    Args:
        query: Search query (company name).

    Returns:
        Extracted news content as plain text.
    """
    url = f"https://news.google.com/search?q={query}"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

                # Extract article headlines and snippets
                articles = await page.evaluate("""
                () => {
                    const results = [];
                    document.querySelectorAll('article').forEach(el => {
                        const headline = el.querySelector('h3')?.textContent || '';
                        const snippet = el.querySelector('[data-snippet]')?.textContent || '';
                        if (headline) results.push(headline + ' ' + snippet);
                    });
                    return results.slice(0, 15).join('\\n');
                }
                """)

                return str(articles or "")
            finally:
                await browser.close()
    except Exception as e:
        print(f"google_news_search error: {e}")
        return ""


async def linkedin_search_jobs(company_name: str) -> str:
    """Search LinkedIn jobs for hiring signals.

    Args:
        company_name: Company to search for.

    Returns:
        Job listings text.
    """
    url = f"https://www.linkedin.com/jobs/search/?keywords={company_name}"
    return await scrape_url(url)


async def naukri_search_jobs(company_name: str) -> str:
    """Search Naukri for hiring signals.

    Args:
        company_name: Company to search for.

    Returns:
        Job listings text.
    """
    url = f"https://www.naukri.com/jobs-{company_name.replace(' ', '-').lower()}"
    return await scrape_url(url)
