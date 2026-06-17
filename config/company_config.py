"""Company configuration and helper for known companies.

Contains COMPANY_CONFIG mapping and helper function to fetch or
construct basic URLs for a company.
"""
from typing import Dict
from urllib.parse import quote_plus

COMPANY_CONFIG: Dict[str, Dict[str, str]] = {
    "asian paints": {
        "investor_url": "https://www.asianpaints.com/more/investors.html",
        "website": "https://www.asianpaints.com",
        "esg_url": "https://sustainability.asianpaints.com",
        "careers_url": "https://www.asianpaints.com/careers.html",
    },
    "dcm shriram": {
        "investor_url": "https://www.dcmshriram.com/investors",
        "website": "https://www.dcmshriram.com",
        "careers_url": "https://www.dcmshriram.com/careers",
    },
}


def get_company_config(company_name: str) -> Dict[str, str]:
    """Return config for a company. If not present, construct basic URLs.

    Args:
        company_name: Human-readable company name.

    Returns:
        Dict with keys 'investor_url', 'website', 'careers_url'.
    """
    key = company_name.strip().lower()
    if key in COMPANY_CONFIG:
        return COMPANY_CONFIG[key]

    # Fallback: construct simple URLs from the name
    base = "https://" + quote_plus(company_name.replace(" ", "")) + ".com"
    return {
        "investor_url": f"{base}/investors",
        "website": base,
        "careers_url": f"{base}/careers",
    }
