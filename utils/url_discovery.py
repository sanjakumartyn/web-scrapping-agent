"""URL discovery and validation utilities for enterprise websites."""

import re
from urllib.parse import urljoin, urlparse
from typing import List, Set, Optional
import aiohttp
from loguru import logger

COMMON_ESG_KEYWORDS = [
    "sustainability", "esg", "environmental", "social", "governance",
    "carbon", "emissions", "renewable", "green", "net-zero",
    "decarbonization", "climate", "climate-action", "corporate-responsibility",
    "responsibility", "csr", "diversity", "inclusion", "inclusion-and-diversity",
    "supply-chain", "ethics", "compliance", "reporting", "waste", "water",
    "biodiversity", "impact", "environment"
]

COMMON_INVESTOR_KEYWORDS = [
    "investor-relations", "ir", "investors", "annual-report",
    "annual-results", "financial", "financial-results", "earnings", "reports",
    "presentation", "shareholder", "10-k", "10-q", "sec-filings", "results"
]

COMMON_CAREERS_KEYWORDS = [
    "careers", "jobs", "job-openings", "hiring", "recruitment", "openings",
    "join-us", "work-with-us", "employment", "opportunities", "life-at",
    "talent", "students", "internships"
]


class URLDiscovery:
    """Discover and validate URLs for specific corporate resources."""

    def __init__(self, base_url: str):
        """Initialize with company base website URL.

        Args:
            base_url: Company website URL (e.g., https://www.example.com)
        """
        self.base_url = base_url.rstrip("/")
        self.domain = urlparse(base_url).netloc

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Validate URL format and accessibility.

        Args:
            url: URL to validate

        Returns:
            True if URL is valid
        """
        try:
            result = urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception as e:
            logger.warning(f"URL validation failed: {e}")
            return False

    def find_esg_url(self, common_paths: List[str] = None) -> Optional[str]:
        """Find ESG/sustainability page URL.

        Args:
            common_paths: Additional paths to try

        Returns:
            ESG page URL if found, None otherwise
        """
        paths = common_paths or [
            "/sustainability",
            "/esg",
            "/corporate-responsibility",
            "/about/sustainability",
            "/sustainability/overview",
            "/csr",
        ]

        for path in paths:
            url = urljoin(self.base_url, path)
            if self.is_valid_url(url):
                return url

        return None

    def find_investor_url(self, common_paths: List[str] = None) -> Optional[str]:
        """Find investor relations page URL.

        Args:
            common_paths: Additional paths to try

        Returns:
            Investor relations URL if found, None otherwise
        """
        paths = common_paths or [
            "/investor-relations",
            "/ir",
            "/investors",
            "/investor_relations",
            "/about/investor-relations",
        ]

        for path in paths:
            url = urljoin(self.base_url, path)
            if self.is_valid_url(url):
                return url

        return None

    def find_careers_url(self, common_paths: List[str] = None) -> Optional[str]:
        """Find careers/jobs page URL.

        Args:
            common_paths: Additional paths to try

        Returns:
            Careers page URL if found, None otherwise
        """
        paths = common_paths or [
            "/careers",
            "/jobs",
            "/hiring",
            "/join-us",
            "/about/careers",
        ]

        for path in paths:
            url = urljoin(self.base_url, path)
            if self.is_valid_url(url):
                return url

        return None

    @staticmethod
    def extract_links_from_html(html: str, base_url: str) -> Set[str]:
        """Extract all links from HTML content.

        Args:
            html: HTML content
            base_url: Base URL for relative link resolution

        Returns:
            Set of absolute URLs
        """
        links = set()
        href_pattern = re.compile(r'href=["\'](.*?)["\']')

        for match in href_pattern.finditer(html):
            href = match.group(1)
            if href.startswith("#"):
                continue

            absolute_url = urljoin(base_url, href)
            if URLDiscovery.is_valid_url(absolute_url):
                links.add(absolute_url)

        return links

    @staticmethod
    def filter_links_by_keywords(links: Set[str], keywords: List[str]) -> Set[str]:
        """Filter links by keywords.

        Args:
            links: Set of URLs to filter
            keywords: Keywords to match

        Returns:
            Filtered set of URLs
        """
        filtered = set()
        keywords_lower = [kw.lower() for kw in keywords]

        for link in links:
            link_lower = link.lower()
            if any(kw in link_lower for kw in keywords_lower):
                filtered.add(link)

        return filtered

    async def discover_resource_urls(self) -> dict:
        """Automatically discover resource URLs (ESG, IR, Careers).

        Returns:
            Dictionary with discovered URLs
        """
        results = {
            "esg_url": self.find_esg_url(),
            "investor_url": self.find_investor_url(),
            "careers_url": self.find_careers_url(),
        }

        logger.info(f"Discovered URLs for {self.domain}: {results}")
        return results
