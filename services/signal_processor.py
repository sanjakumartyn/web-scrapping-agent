"""Rule-based signal processing for raw sales intelligence signals.

This module converts noisy raw signals into clean, deduplicated, actionable
records that can be consumed by UI and downstream systems.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


INTENT_MAP = {
    "expansion": "growth",
    "hiring": "growth",
    "competitor_activity": "risk",
    "financial_decline": "risk",
}


def _normalize_text(value: Any) -> str:
    """Return a compact, whitespace-normalized string."""
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_description(description: str) -> List[str]:
    """Split a messy description into useful chunks."""
    if not description:
        return []
    parts = [part.strip() for part in str(description).split("|")]
    return [part for part in parts if part]


def extract_title(description: str) -> str:
    """Extract a short readable title from a messy signal description."""
    text = _normalize_text(description)
    if not text:
        return ""

    parts = _split_description(text)
    candidates: List[str] = []

    for part in parts:
        cleaned = part.strip(" -:;,.[]()")
        if cleaned:
            candidates.append(cleaned)

    if candidates:
        # Prefer the most informative fragment, not just the first label-like token.
        scored_candidates = []
        for index, candidate in enumerate(candidates):
            lowered = candidate.lower()
            score = len(candidate)
            if any(keyword in lowered for keyword in ["investment", "expand", "expansion", "plant", "factory", "capacity", "hiring", "acquisition", "partnership"]):
                score += 60
            if re.search(r"[₹$]|\b\d+[,.\d]*\s?(cr|crore|million|billion|mn|bn)\b", candidate, re.IGNORECASE):
                score += 40
            if index == 0 and len(candidate) < 20:
                score -= 30
            scored_candidates.append((score, candidate))

        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        return scored_candidates[0][1][:120]

    # Fallback to the first readable portion of the full text.
    return text[:80].rstrip()


def extract_summary(description: str) -> str:
    """Return the last meaningful portion of a noisy description."""
    text = _normalize_text(description)
    if not text:
        return ""

    parts = _split_description(text)
    if parts:
        summary = parts[-1]
    else:
        summary = text

    summary = summary.strip(" -:;,.[]()")
    if len(summary) > 200:
        summary = summary[:197].rstrip() + "..."
    return summary


def assign_impact_score(signal: Dict[str, Any]) -> int:
    """Assign a rule-based impact score from 0 to 100."""
    signal_type = _normalize_text(signal.get("signal_type") or signal.get("type")).lower()
    description = _normalize_text(signal.get("description") or signal.get("raw_snippet"))
    searchable = f"{signal_type} {description}".lower()

    if any(keyword in searchable for keyword in ["investment", "invest", "expansion", "expand", "plant", "factory", "capacity"]):
        return 92
    if signal_type == "hiring" or any(keyword in searchable for keyword in ["hiring", "recruit", "headcount", "job", "open position", "talent"]):
        return 78
    if signal_type == "competitor_activity" or any(keyword in searchable for keyword in ["competitor", "competition", "rival", "market share", "acquisition", "merger"]):
        return 70
    if signal_type == "financial_decline" or any(keyword in searchable for keyword in ["decline", "loss", "downturn", "revenue fall", "profit fall", "cut"]):
        return 66

    return 60


def assign_priority(score: int) -> str:
    """Map impact score to a priority bucket."""
    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def _description_similarity(left: str, right: str) -> float:
    """Return a lightweight similarity score for two text snippets."""
    left_norm = _normalize_text(left).lower()
    right_norm = _normalize_text(right).lower()
    if not left_norm or not right_norm:
        return 0.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def remove_duplicates(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate signals by title or by description similarity."""
    deduped: List[Dict[str, Any]] = []

    for signal in signals:
        title = _normalize_text(signal.get("title")).lower()
        description = _normalize_text(signal.get("summary") or signal.get("description") or signal.get("raw_snippet"))

        is_duplicate = False
        for existing in deduped:
            existing_title = _normalize_text(existing.get("title")).lower()
            existing_description = _normalize_text(existing.get("summary") or existing.get("description") or existing.get("raw_snippet"))

            if title and existing_title and title == existing_title:
                is_duplicate = True
                break

            similarity = _description_similarity(description, existing_description)
            if similarity >= 0.88:
                is_duplicate = True
                break

        if not is_duplicate:
            deduped.append(signal)

    return deduped


def _flatten_raw_signals(raw_signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Support either a flat list of signals or wrapper payloads with a signals array."""
    flattened: List[Dict[str, Any]] = []

    for item in raw_signals or []:
        if not isinstance(item, dict):
            continue

        if isinstance(item.get("signals"), list):
            account_id = _normalize_text(item.get("account_id"))
            company_name = _normalize_text(item.get("company_name"))
            for signal in item.get("signals", []):
                if not isinstance(signal, dict):
                    continue
                merged = dict(signal)
                merged.setdefault("account_id", account_id)
                merged.setdefault("company_name", company_name)
                flattened.append(merged)
        else:
            flattened.append(dict(item))

    return flattened


def process_signals(raw_signals: list) -> list:
    """Convert raw signals into clean, actionable, deduplicated records."""
    flattened = _flatten_raw_signals(raw_signals)
    logger.info("Processing %d raw signals", len(flattened))

    processed: List[Dict[str, Any]] = []

    for raw in flattened:
        description = _normalize_text(raw.get("description") or raw.get("raw_snippet"))
        signal_type = _normalize_text(raw.get("signal_type") or raw.get("type")).lower()
        title = extract_title(description)
        summary = extract_summary(description)
        impact_score = assign_impact_score(raw)
        priority = assign_priority(impact_score)
        intent = INTENT_MAP.get(signal_type, "neutral")

        processed.append(
            {
                "account_id": _normalize_text(raw.get("account_id")),
                "type": signal_type,
                "title": title,
                "summary": summary,
                "intent": intent,
                "impact_score": impact_score,
                "priority": priority,
                "confidence_score": raw.get("confidence_score", raw.get("confidence", 0)),
                "source_type": raw.get("source_type"),
            }
        )

    deduped = remove_duplicates(processed)
    logger.info("Deduplicated signals: %d -> %d", len(processed), len(deduped))
    return deduped
