"""Direct Playwright-based web scraping without LLM reasoning."""
import asyncio
from typing import Optional
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


HTTP_SCRAPE_TIMEOUT_SECONDS = 5
HTTP_MIN_TEXT_CHARS = 250


def _scrape_url_http(url: str) -> str:
    response = requests.get(
        url,
        timeout=HTTP_SCRAPE_TIMEOUT_SECONDS,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup.get_text("\n", strip=True)


async def scrape_url(url: str, timeout: int = 30000) -> str:
    """Scrape content from a URL using Playwright.

    Args:
        url: The URL to scrape.
        timeout: Maximum time in milliseconds to wait for navigation.

    Returns:
        Text content from the page, or empty string on failure.
    """
    try:
        http_text = await asyncio.to_thread(_scrape_url_http, url)
        if http_text and len(http_text) >= HTTP_MIN_TEXT_CHARS:
            return http_text
    except Exception:
        pass

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.route("**/*", _block_heavy_assets)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                # Give dynamic text a short settle window without holding the pipeline.
                await asyncio.sleep(0.75)
                # Extract all text content
                text = await page.evaluate("() => document.body.innerText")
                return str(text or "")
            finally:
                await browser.close()
    except Exception as e:
        print(f"scrape_url error for {url}: {e}")
        return ""


async def _block_heavy_assets(route) -> None:
    if route.request.resource_type in {"image", "media", "font"}:
        await route.abort()
        return
    await route.continue_()


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
                await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                await asyncio.sleep(1)

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
