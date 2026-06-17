"""Utilities for normalizing and scoring account intelligence signals."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def trim_text(text: str, limit: int = 50000) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    return cleaned[:limit]


def clamp_float(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number <= 1 and maximum > 1:
        number *= maximum
    return max(minimum, min(maximum, number))


def clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    return int(round(clamp_float(value, minimum, maximum, default)))


def extract_source_date(text: str) -> Optional[str]:
    """Extract a best-effort date from snippets or NewsAPI formatted lines."""
    if not text:
        return None

    iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})", text)
    if iso_match:
        return iso_match.group(0)

    month_match = re.search(
        r"\b("
        + "|".join(MONTHS.keys())
        + r")\.?\s+(\d{1,2}),?\s+(20\d{2})\b",
        text,
        flags=re.IGNORECASE,
    )
    if month_match:
        month = MONTHS[month_match.group(1).lower().rstrip(".")]
        day = int(month_match.group(2))
        year = int(month_match.group(3))
        try:
            return datetime(year, month, day).date().isoformat()
        except ValueError:
            return None

    year_match = re.search(r"\b(20\d{2})\b", text)
    if year_match:
        return f"{year_match.group(1)}-01-01"
    return None


def calculate_recency_score(source_date: Optional[str]) -> int:
    if not source_date:
        return 55

    try:
        parsed = datetime.fromisoformat(source_date[:10]).replace(tzinfo=timezone.utc)
    except ValueError:
        return 55

    age_days = max(0, (utc_now() - parsed).days)
    if age_days <= 30:
        return 100
    if age_days <= 90:
        return 85
    if age_days <= 180:
        return 70
    if age_days <= 365:
        return 55
    if age_days <= 730:
        return 40
    return 25


def calculate_priority_score(recency_score: int, relevance_score: int, confidence_score: float) -> int:
    confidence_100 = clamp_float(confidence_score, 0, 1, 0.5) * 100
    score = relevance_score * 0.45 + confidence_100 * 0.35 + recency_score * 0.20
    return clamp_int(score, 0, 100, 50)


def stable_signal_id(account_id: str, agent_name: str, title: str, evidence: str) -> str:
    seed = "|".join([account_id or "", agent_name or "", title or "", evidence or ""])
    return hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:16]


def keyword_relevance(text: str, keywords: Iterable[str], base: int = 62) -> int:
    lowered = (text or "").lower()
    hits = sum(1 for keyword in keywords if keyword.lower() in lowered)
    return clamp_int(base + hits * 8, 0, 95, base)


def split_sentences(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if len(part.strip()) >= 40]


def matching_sentences(text: str, keywords: Iterable[str], limit: int = 6) -> List[str]:
    lowered_keywords = [keyword.lower() for keyword in keywords]
    matches: List[str] = []
    for sentence in split_sentences(text):
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in lowered_keywords):
            matches.append(sentence[:500])
        if len(matches) >= limit:
            break
    return matches


def normalize_signal(raw: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize LLM or rule output into the dashboard-facing signal schema."""
    detected_at = defaults.get("detected_at") or utc_now_iso()
    evidence = str(raw.get("evidence") or raw.get("raw_snippet") or raw.get("description") or "").strip()
    title = str(raw.get("title") or raw.get("signal_type") or defaults.get("signal_type") or "Signal").strip()
    description = str(raw.get("description") or evidence or title).strip()
    signal_type = str(raw.get("signal_type") or defaults.get("signal_type") or "business_signal").strip().lower()
    source_date = raw.get("source_date") or extract_source_date(evidence) or extract_source_date(description)
    recency_score = clamp_int(raw.get("recency_score"), 0, 100, calculate_recency_score(source_date))
    relevance_score = clamp_int(raw.get("relevance_score"), 0, 100, defaults.get("relevance_score", 65))
    confidence_score = clamp_float(raw.get("confidence_score", raw.get("confidence")), 0, 1, defaults.get("confidence_score", 0.65))
    priority_score = clamp_int(
        raw.get("priority_score"),
        0,
        100,
        calculate_priority_score(recency_score, relevance_score, confidence_score),
    )

    normalized = {
        "signal_id": stable_signal_id(defaults.get("account_id", ""), defaults.get("agent", ""), title, evidence),
        "account_id": defaults.get("account_id"),
        "company_name": defaults.get("company_name"),
        "agent": defaults.get("agent"),
        "category": defaults.get("category"),
        "signal_type": signal_type,
        "classification": str(raw.get("classification") or defaults.get("classification") or "opportunity").lower(),
        "title": title[:140],
        "description": description[:700],
        "evidence": evidence[:1000],
        "source_type": raw.get("source_type") or defaults.get("source_type"),
        "source_date": source_date,
        "detected_at": detected_at,
        "confidence_score": round(confidence_score, 2),
        "recency_score": recency_score,
        "relevance_score": relevance_score,
        "priority_score": priority_score,
        "reasoning": str(raw.get("reasoning") or raw.get("llm_reason") or "").strip()[:500],
        "demand_trigger": str(raw.get("demand_trigger") or defaults.get("demand_trigger") or "").strip(),
        "solution_area": str(raw.get("solution_area") or defaults.get("solution_area") or "").strip(),
        "recommended_action": str(raw.get("recommended_action") or defaults.get("recommended_action") or "").strip(),
    }

    for optional_key in ("role_category", "supplier_name", "switching_signal", "metric", "timeframe"):
        if raw.get(optional_key):
            normalized[optional_key] = raw.get(optional_key)

    return normalized


def dedupe_signals(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for signal in sorted(signals, key=lambda item: item.get("priority_score", 0), reverse=True):
        key = (
            str(signal.get("signal_type", "")).lower(),
            re.sub(r"[^a-z0-9]+", " ", str(signal.get("title", "")).lower()).strip()[:90],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(signal)
    return deduped
