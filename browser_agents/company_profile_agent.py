"""Browser agent that extracts a structured profile from official company pages."""
import re
from typing import Any, Dict, List, Set
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright

from layer1_agents.utils.text_processing import TextProcessor


PROFILE_LINK_KEYWORDS = [
    "about",
    "company",
    "overview",
    "product",
    "products",
    "service",
    "services",
    "solution",
    "solutions",
    "brand",
    "brands",
    "business",
    "segment",
    "segments",
    "industry",
    "industries",
]

COMMON_PROFILE_PATHS = [
    "/about",
    "/about-us",
    "/about.html",
    "/company",
    "/products",
    "/products.html",
    "/services",
    "/services.html",
    "/brands",
    "/business",
    "/businesses",
    "/solutions",
    "/industries",
]

SECTION_KEYWORDS = {
    "products": ["product", "products", "range", "portfolio", "category", "categories"],
    "services": ["service", "services", "solution", "solutions", "offering", "offerings"],
    "brands": ["brand", "brands"],
    "industries_served": ["industry", "industries", "sector", "sectors", "markets served"],
    "business_segments": ["business", "segment", "segments", "division", "divisions", "vertical"],
}

ITEM_SKIP_PATTERNS = [
    "cookie",
    "privacy",
    "terms",
    "copyright",
    "all rights",
    "contact",
    "login",
    "sign in",
    "search",
    "menu",
    "read more",
    "learn more",
    "view all",
    "download",
    "subscribe",
    "follow us",
    "javascript",
    "book free",
    "call",
    "contractor",
    "construction",
    "hired",
    "submit",
    "update me",
    "whatsapp",
]

GENERIC_ITEM_NAMES = {
    "about",
    "all",
    "brands",
    "business",
    "calculators",
    "careers",
    "company",
    "explore",
    "home",
    "more",
    "next",
    "now",
    "previous",
    "products",
    "professionals",
    "services",
    "solutions",
    "sustainability",
}

DESCRIPTION_SKIP_PATTERNS = [
    "+91",
    "book a free",
    "contractors to get in touch",
    "explore now",
    "submit",
    "update me on whatsapp",
    "view colour",
    "watch video",
    "whatsapp",
    "previous",
    "next",
    "menu",
]

PROFILE_NAVIGATION_TIMEOUT_MS = 30000
PROFILE_NETWORK_IDLE_WAIT_MS = 6000
PROFILE_TEXT_WAIT_MS = 10000
PROFILE_SETTLE_WAIT_MS = 3000
MIN_PROFILE_TEXT_CHARS = 300


def _empty_profile(company_name: str, website: str) -> Dict[str, Any]:
    return {
        "company_name": company_name,
        "website": website,
        "description": "",
        "products": [],
        "services": [],
        "brands": [],
        "industries_served": [],
        "business_segments": [],
        "source_urls": [],
        "confidence_score": 0.0,
    }


def _same_domain(url: str, root_url: str) -> bool:
    root_host = urlparse(root_url).netloc.lower().removeprefix("www.")
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return bool(host) and host == root_host


def _is_relevant_url(url: str) -> bool:
    lowered = url.lower()
    return any(keyword in lowered for keyword in PROFILE_LINK_KEYWORDS)


def _clean_item(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip(" -:;,.|")
    value = re.sub(r"^(our|all|explore|view)\s+", "", value, flags=re.IGNORECASE)
    return value.strip()


def _is_good_item(value: str) -> bool:
    value = _clean_item(value)
    lowered = value.lower()
    if len(value) < 3 or len(value) > 90:
        return False
    if lowered in GENERIC_ITEM_NAMES:
        return False
    if any(pattern in lowered for pattern in ITEM_SKIP_PATTERNS):
        return False
    if lowered.count(" ") > 8:
        return False
    if re.fullmatch(r"[\W\d_]+", value):
        return False
    return True


def _dedupe_items(items: List[Dict[str, str]], limit: int = 20) -> List[Dict[str, str]]:
    seen: Set[str] = set()
    deduped: List[Dict[str, str]] = []
    for item in items:
        name = _clean_item(item.get("name", ""))
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        deduped.append({"name": name, "source_url": item.get("source_url", "")})
        if len(deduped) >= limit:
            break
    return deduped


def _candidate_lines(text: str) -> List[str]:
    lines = []
    for raw_line in (text or "").splitlines():
        line = _clean_item(raw_line)
        if _is_good_item(line):
            lines.append(line)
    return lines


def _extract_description(company_name: str, pages: List[Dict[str, Any]]) -> str:
    company_key = company_name.lower()
    for page in pages:
        meta_description = TextProcessor.clean_text(page.get("meta_description", ""))
        if meta_description:
            lowered_meta = meta_description.lower()
            if not any(pattern in lowered_meta for pattern in DESCRIPTION_SKIP_PATTERNS):
                return meta_description[:350].strip()

        text = TextProcessor.clean_text(page.get("text", ""))
        sentences = TextProcessor.extract_sentences(text)
        for sentence in sentences[:30]:
            lowered = sentence.lower()
            if any(pattern in lowered for pattern in DESCRIPTION_SKIP_PATTERNS):
                continue
            if company_key in lowered and any(word in lowered for word in ["is ", "are ", "company", "manufacturer", "provider", "leader"]):
                return sentence[:350].strip()
    return ""


def _extract_structured_items(pages: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
    extracted: Dict[str, List[Dict[str, str]]] = {
        "products": [],
        "services": [],
        "brands": [],
        "industries_served": [],
        "business_segments": [],
    }

    for page in pages:
        url = page.get("url", "")
        title = _clean_item(page.get("title", ""))
        title_lower = title.lower()
        url_lower = url.lower()
        lines = _candidate_lines(page.get("text", ""))

        for field, keywords in SECTION_KEYWORDS.items():
            page_is_relevant = any(keyword in url_lower or keyword in title_lower for keyword in keywords)
            if page_is_relevant and _is_good_item(title):
                extracted[field].append({"name": title, "source_url": url})

            for index, line in enumerate(lines):
                lowered = line.lower()
                is_heading = any(keyword in lowered for keyword in keywords)
                if not is_heading:
                    continue

                if _is_good_item(line) and not lowered.endswith("?"):
                    extracted[field].append({"name": line, "source_url": url})

                for nearby in lines[index + 1 : index + 6]:
                    if _is_good_item(nearby):
                        extracted[field].append({"name": nearby, "source_url": url})

    return {field: _dedupe_items(items) for field, items in extracted.items()}


async def _scrape_profile_page(page: Any, url: str, timeout: int) -> Dict[str, Any]:
    await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    try:
        await page.wait_for_load_state(
            "networkidle",
            timeout=min(timeout, PROFILE_NETWORK_IDLE_WAIT_MS),
        )
    except Exception:
        pass
    try:
        await page.wait_for_function(
            """
            (minChars) => document.body
                && document.body.innerText
                && document.body.innerText.trim().length >= minChars
            """,
            arg=MIN_PROFILE_TEXT_CHARS,
            timeout=min(timeout, PROFILE_TEXT_WAIT_MS),
        )
    except Exception:
        pass
    await page.wait_for_timeout(PROFILE_SETTLE_WAIT_MS)
    data = await page.evaluate(
        """
        () => ({
            title: document.title || "",
            meta_description: document.querySelector('meta[name="description"]')?.content || "",
            text: document.body ? document.body.innerText : "",
            links: Array.from(document.querySelectorAll("a[href]"))
                .map((anchor) => anchor.href)
                .filter(Boolean)
        })
        """
    )
    data["url"] = url
    return data


def _rank_urls(urls: Set[str], website: str) -> List[str]:
    def score(url: str) -> int:
        lowered = url.lower()
        value = 0
        for index, keyword in enumerate(PROFILE_LINK_KEYWORDS):
            if keyword in lowered:
                value += max(1, 30 - index)
        if url.rstrip("/") == website.rstrip("/"):
            value += 100
        return value

    return sorted(urls, key=score, reverse=True)


async def collect_company_profile(company_name: str, website: str, max_pages: int = 8) -> Dict[str, Any]:
    """Collect official company product and service details from its website."""
    profile = _empty_profile(company_name, website)
    if not website:
        return profile

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                candidates: Set[str] = {website}
                for path in COMMON_PROFILE_PATHS:
                    candidates.add(urljoin(website.rstrip("/") + "/", path.lstrip("/")))

                homepage = await _scrape_profile_page(page, website, timeout=PROFILE_NAVIGATION_TIMEOUT_MS)
                pages: List[Dict[str, Any]] = [homepage]

                for link in homepage.get("links", []):
                    normalized = link.split("#", 1)[0].rstrip("/")
                    if _same_domain(normalized, website) and _is_relevant_url(normalized):
                        candidates.add(normalized)

                for url in _rank_urls(candidates, website):
                    if len(pages) >= max_pages:
                        break
                    if url == website or not _same_domain(url, website):
                        continue
                    try:
                        pages.append(await _scrape_profile_page(page, url, timeout=PROFILE_NAVIGATION_TIMEOUT_MS))
                    except Exception as e:
                        print(f"collect_company_profile page skipped {url}: {e}")

                items = _extract_structured_items(pages)
                profile.update(items)
                profile["description"] = _extract_description(company_name, pages)
                profile["source_urls"] = list(dict.fromkeys(page_data.get("url", "") for page_data in pages if page_data.get("url")))

                filled_sections = sum(1 for field in SECTION_KEYWORDS if profile.get(field))
                source_score = min(len(profile["source_urls"]), 5) * 0.04
                profile["confidence_score"] = round(min(0.95, 0.25 + filled_sections * 0.15 + source_score), 2)
                return profile
            finally:
                await browser.close()
    except Exception as e:
        print(f"collect_company_profile error: {e}")
        return profile
