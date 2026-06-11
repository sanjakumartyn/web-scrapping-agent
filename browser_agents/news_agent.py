"""Browser agent that collects company news from NewsAPI first."""
import asyncio
from datetime import datetime, timedelta
import os
from typing import Dict, List, Optional
from urllib.parse import urlparse

import aiohttp

from layer1_agents.browser_agents.playwright_scraper import google_news_search
from layer1_agents.config.company_config import get_company_config


BUSINESS_QUERY_TERMS = [
    "earnings",
    "results",
    "acquisition",
    "expansion",
    "hiring",
    "partnership",
    "sustainability",
    "investor relations",
    "press release",
]


def _format_news_articles(articles: List[Dict]) -> str:
    """Convert article payloads into plain text for the rule engine."""
    lines = []
    for article in articles:
        query_label = (article.get("_query_label") or "").strip()
        title = (article.get("title") or "").strip()
        description = (article.get("description") or "").strip()
        source = (article.get("source") or {}).get("name") or ""
        published_at = (article.get("publishedAt") or "").strip()
        url = (article.get("url") or "").strip()

        parts = [part for part in [title, description, source, published_at, url] if part]
        if parts:
            if query_label:
                parts.insert(0, f"[{query_label}]")
            lines.append(" | ".join(parts))

    return "\n".join(lines)


def _extract_domain(website_url: Optional[str]) -> str:
    """Extract a clean domain name from a website URL."""
    if not website_url:
        return ""

    parsed = urlparse(website_url)
    domain = (parsed.netloc or "").lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _build_search_requests(company_name: str, website_url: Optional[str]) -> List[Dict[str, str]]:
    """Build a small set of NewsAPI queries focused on company news."""
    domain = _extract_domain(website_url)
    business_query = f'{company_name} ({" OR ".join(BUSINESS_QUERY_TERMS)})'

    requests = [
        {
            "label": "company-name",
            "params": {
                "q": company_name,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 10,
            },
        },
        {
            "label": "company-business",
            "params": {
                "q": business_query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 10,
            },
        },
        {
            "label": "title-match",
            "params": {
                "qInTitle": company_name,
                "language": "en",
                "sortBy": "relevancy",
                "pageSize": 10,
            },
        },
    ]

    if domain:
        requests.append(
            {
                "label": "official-domain",
                "params": {
                    "q": company_name,
                    "domains": domain,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 10,
                },
            }
        )

    return requests


async def _search_news_api(session: aiohttp.ClientSession, api_key: str, company_name: str, params: Dict[str, str], label: str) -> List[Dict]:
    """Run one NewsAPI search and return articles tagged with the query label."""
    url = "https://newsapi.org/v2/everything"
    query_params = dict(params)
    query_params["apiKey"] = api_key
    query_params["from"] = (datetime.utcnow() - timedelta(days=30)).date().isoformat()

    try:
        async with session.get(url, params=query_params) as response:
            if response.status != 200:
                text = await response.text()
                print(f"news_agent NewsAPI error {response.status} ({label}): {text[:200]}")
                return []

            payload = await response.json()
            articles = payload.get("articles", []) or []
            for article in articles:
                article["_query_label"] = label
                article["_company_name"] = company_name
            return articles
    except Exception as e:
        print(f"news_agent NewsAPI error ({label}): {e}")
        return []


async def _collect_news_api(company_name: str) -> str:
    """Collect recent news for a company using several NewsAPI queries."""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        return ""

    try:
        company_cfg = get_company_config(company_name)
        search_requests = _build_search_requests(company_name, company_cfg.get("website"))
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            results = await asyncio.gather(
                *[
                    _search_news_api(session, api_key, company_name, request["params"], request["label"])
                    for request in search_requests
                ],
                return_exceptions=True,
            )

        articles_by_url: Dict[str, Dict] = {}
        for result in results:
            if isinstance(result, Exception):
                print(f"news_agent NewsAPI batch error: {result}")
                continue
            for article in result:
                url = (article.get("url") or "").strip()
                if not url:
                    continue
                articles_by_url.setdefault(url, article)

        articles = list(articles_by_url.values())
        if not articles:
            return ""

        return _format_news_articles(articles[:20])
    except Exception as e:
        print(f"news_agent NewsAPI error: {e}")
        return ""


async def collect_news(company_name: str) -> str:
    """Collect recent news for the company.

    Tries NewsAPI first, then falls back to Google News scraping if no API key
    is configured or the API request fails. Returns plain text.

    Errors are caught and an empty string is returned on failure.
    """
    try:
        news = await _collect_news_api(company_name)
        if news:
            return news

        return await google_news_search(company_name)
    except Exception as e:
        print(f"news_agent error: {e}")
        return ""
