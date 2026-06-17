"""Competitive and supplier relationship signal analysis agent."""

from __future__ import annotations

from typing import Any, Dict, List

from .llm_client import generate_json
from .signal_utils import keyword_relevance, matching_sentences, normalize_signal, trim_text, utc_now_iso


AGENT_NAME = "competitive_signal_agent"
ALLOWED_TYPES = [
    "supplier_relationship",
    "supplier_switching_signal",
    "vendor_change",
    "competitive_move",
    "strategic_partnership",
]
KEYWORDS = [
    "supplier",
    "vendor",
    "procurement",
    "sourcing",
    "selected",
    "awarded",
    "contract",
    "partnership",
    "alliance",
    "collaboration",
    "switch",
    "replace",
    "alternative supplier",
    "new supplier",
    "distribution agreement",
    "acquisition",
    "merger",
]


def _prompt(company_name: str, public_text: str) -> str:
    return f"""
You are the competitive signal agent for B2B account intelligence.
Detect supplier relationships, vendor changes, switching signals, strategic partnerships, and competitive moves for {company_name}.

Return JSON only:
{{
  "signals": [
    {{
      "signal_type": "supplier_relationship|supplier_switching_signal|vendor_change|competitive_move|strategic_partnership",
      "classification": "opportunity|risk|monitor",
      "title": "short competitive signal title",
      "description": "what relationship or competitive move was detected",
      "evidence": "short public mention evidence",
      "source_date": "YYYY-MM-DD or null",
      "supplier_name": "supplier/vendor/partner name if stated",
      "switching_signal": "new supplier|vendor replacement|contract award|partnership|unknown",
      "confidence_score": 0.0,
      "recency_score": 0,
      "relevance_score": 0,
      "reasoning": "why this matters for account strategy",
      "recommended_action": "next action"
    }}
  ]
}}

Rules:
- Maximum 6 signals.
- Only extract supplier or competitive relationships explicitly supported by text.
- Do not invent supplier names.
- Treat acquisitions, partnerships, and vendor awards as competitive context when supplier switching is not explicit.

Public text:
{trim_text(public_text, 45000)}
""".strip()


def _fallback(company_name: str, account_id: str, public_text: str, detected_at: str) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    for sentence in matching_sentences(public_text, KEYWORDS, limit=8):
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in ["switch", "replace", "alternative supplier", "new supplier", "vendor change"]):
            signal_type = "supplier_switching_signal"
            switching_signal = "supplier or vendor switching"
        elif any(keyword in lowered for keyword in ["supplier", "vendor", "sourcing", "procurement"]):
            signal_type = "supplier_relationship"
            switching_signal = "supplier relationship"
        elif any(keyword in lowered for keyword in ["partnership", "alliance", "collaboration", "agreement"]):
            signal_type = "strategic_partnership"
            switching_signal = "partnership"
        else:
            signal_type = "competitive_move"
            switching_signal = "competitive context"

        signals.append(
            normalize_signal(
                {
                    "signal_type": signal_type,
                    "title": sentence[:100],
                    "description": sentence,
                    "evidence": sentence,
                    "switching_signal": switching_signal,
                    "confidence_score": 0.6,
                    "relevance_score": keyword_relevance(sentence, KEYWORDS, base=63),
                    "reasoning": "Matched public competitive or supplier relationship language.",
                    "recommended_action": "Check whether this creates displacement, partnership, or account-entry opportunity.",
                },
                {
                    "account_id": account_id,
                    "company_name": company_name,
                    "agent": AGENT_NAME,
                    "category": "competitive",
                    "source_type": "public_mentions",
                    "detected_at": detected_at,
                },
            )
        )
    return signals[:6]


def analyze_competitive_signals(
    company_name: str,
    account_id: str,
    raw_sources: Dict[str, str],
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Extract competitive and supplier relationship signals."""
    detected_at = utc_now_iso()
    public_text = "\n\n".join(
        [
            raw_sources.get("news", ""),
            raw_sources.get("annual_report", ""),
            raw_sources.get("esg", ""),
        ]
    )
    if not public_text.strip():
        return {"agent": AGENT_NAME, "status": "empty", "signals": []}

    payload = generate_json(_prompt(company_name, public_text)) if use_llm else None
    raw_signals = payload.get("signals", []) if isinstance(payload, dict) else []
    signals: List[Dict[str, Any]] = []

    for raw in raw_signals:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("signal_type", "")).lower() not in ALLOWED_TYPES:
            continue
        signals.append(
            normalize_signal(
                raw,
                {
                    "account_id": account_id,
                    "company_name": company_name,
                    "agent": AGENT_NAME,
                    "category": "competitive",
                    "source_type": "public_mentions",
                    "detected_at": detected_at,
                    "confidence_score": 0.66,
                    "relevance_score": 66,
                    "classification": "monitor",
                },
            )
        )

    if not signals:
        signals = _fallback(company_name, account_id, public_text, detected_at)

    return {"agent": AGENT_NAME, "status": "completed", "signals": signals}
