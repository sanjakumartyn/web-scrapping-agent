"""Browser agent that finds and extracts investor reports from investor relations pages."""

import asyncio
import os
import tempfile
from typing import List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from layer1_agents.browser_agents.playwright_scraper import scrape_url
from layer1_agents.utils.pdf_extraction import PDFExtractor


REPORT_PAGE_TIMEOUT_MS = 5000
REPORT_HTTP_TIMEOUT_SECONDS = 8
REPORT_PDF_TIMEOUT_SECONDS = 15
MAX_REPORT_PDF_LINKS = 2
MAX_REPORT_PDF_PAGES = 20
MAX_REPORT_TEXT_CHARS = 70000


def _discover_annual_report_pdfs(investor_url: str) -> List[str]:
    if not investor_url:
        return []

    try:
        response = requests.get(
            investor_url,
            timeout=REPORT_HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
    except Exception as exc:
        print(f"report_agent PDF discovery error: {exc}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    pdf_urls: List[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        label = anchor.get_text(" ", strip=True)
        combined = f"{href} {label}".lower()
        if ".pdf" not in combined:
            continue
        if not any(keyword in combined for keyword in ["annual", "integrated", "report", "financial"]):
            continue
        absolute_url = urljoin(response.url, href)
        if absolute_url not in pdf_urls:
            pdf_urls.append(absolute_url)
        if len(pdf_urls) >= MAX_REPORT_PDF_LINKS:
            break
    return pdf_urls


def _download_and_extract_pdf(pdf_url: str) -> str:
    tmp_path = ""
    try:
        response = requests.get(
            pdf_url,
            timeout=REPORT_PDF_TIMEOUT_SECONDS,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        if "pdf" not in response.headers.get("content-type", "").lower() and not pdf_url.lower().endswith(".pdf"):
            return ""

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        extracted = PDFExtractor.extract_text(tmp_path, max_pages=MAX_REPORT_PDF_PAGES)
        if extracted:
            return f"PDF source: {pdf_url}\n{extracted[:MAX_REPORT_TEXT_CHARS]}"
        return ""
    except Exception as exc:
        print(f"report_agent PDF extraction error for {pdf_url}: {exc}")
        return ""
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _collect_pdf_report_text(investor_url: str) -> str:
    pdf_texts = []
    for pdf_url in _discover_annual_report_pdfs(investor_url):
        text = _download_and_extract_pdf(pdf_url)
        if text:
            pdf_texts.append(text)
    return "\n\n".join(pdf_texts)


async def collect_report(company_name: str, investor_url: str) -> str:
    """Collect text from investor relations pages and reports.

    Scrapes the investor_url for financial documents, annual reports, and
    sustainability information. Returns plain text content.

    Errors are caught and an empty string is returned on failure.
    """
    try:
        page_task = scrape_url(investor_url, timeout=REPORT_PAGE_TIMEOUT_MS)
        pdf_task = asyncio.to_thread(_collect_pdf_report_text, investor_url)
        page_text, pdf_text = await asyncio.gather(page_task, pdf_task, return_exceptions=True)

        parts = []
        if page_text and not isinstance(page_text, Exception):
            parts.append(str(page_text))
        if pdf_text and not isinstance(pdf_text, Exception):
            parts.append(str(pdf_text))
        return "\n\n".join(parts)
    except Exception as e:
        print(f"report_agent error: {e}")
        return ""
