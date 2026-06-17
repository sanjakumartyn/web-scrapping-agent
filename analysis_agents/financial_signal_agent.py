"""Financial signal analysis agent."""

from __future__ import annotations

from typing import Any, Dict, List

from .llm_client import generate_json
from .signal_utils import keyword_relevance, matching_sentences, normalize_signal, trim_text, utc_now_iso


AGENT_NAME = "financial_signal_agent"
ALLOWED_TYPES = ["growth_trajectory", "capex_commitment", "strategic_priority"]
KEYWORDS = {
    "growth_trajectory": [
        "growth",
        "revenue",
        "volume",
        "capacity",
        "margin",
        "market share",
        "cagr",
        "sales",
    ],
    "capex_commitment": [
        "capex",
        "capital expenditure",
        "capital investment",
        "investment",
        "plant",
        "capacity expansion",
        "project",
    ],
    "strategic_priority": [
        "strategy",
        "strategic",
        "priority",
        "focus",
        "transformation",
        "innovation",
        "sustainability",
        "digital",
    ],
}


def _prompt(company_name: str, annual_report_text: str) -> str:
    allowed = ", ".join(ALLOWED_TYPES)
    return f"""
You are the financial signal agent for B2B account intelligence.
Extract only decision-useful financial signals for {company_name} from the annual report or investor text.

Signal types allowed: {allowed}.

For each signal, reason about:
- growth trajectory: growth direction, segment growth, demand momentum, margin trajectory, capacity-led growth
- capex commitment: announced capital expenditure, plant investments, manufacturing investments, capacity spend
- strategic priority: explicit leadership priorities, operating focus, digital/ESG/growth priorities

Return JSON only:
{{
  "signals": [
    {{
      "signal_type": "growth_trajectory|capex_commitment|strategic_priority",
      "classification": "opportunity|risk|monitor",
      "title": "short business title",
      "description": "specific account intelligence summary",
      "evidence": "short source quote or close paraphrase",
      "source_date": "YYYY-MM-DD or null",
      "metric": "amount/percentage/timeframe if present",
      "timeframe": "FY/year/quarter if present",
      "confidence_score": 0.0,
      "recency_score": 0,
      "relevance_score": 0,
      "reasoning": "why this matters for sales",
      "recommended_action": "next sales action"
    }}
  ]
}}

Rules:
- Maximum 6 signals.
- Do not invent facts, dates, metrics, or initiatives.
- Use null when a date is unavailable.
- Score relevance by likely B2B sales usefulness.

Source text:
{trim_text(annual_report_text, 45000)}
""".strip()


def _fallback(company_name: str, account_id: str, annual_report_text: str, detected_at: str) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    for signal_type, keywords in KEYWORDS.items():
        for sentence in matching_sentences(annual_report_text, keywords, limit=2):
            title = {
                "growth_trajectory": "Financial growth trajectory signal",
                "capex_commitment": "Capex or manufacturing investment signal",
                "strategic_priority": "Strategic priority signal",
            }[signal_type]
            relevance = keyword_relevance(sentence, keywords, base=66)
            signals.append(
                normalize_signal(
                    {
                        "signal_type": signal_type,
                        "title": title,
                        "description": sentence,
                        "evidence": sentence,
                        "confidence_score": 0.62,
                        "relevance_score": relevance,
                        "reasoning": "Matched financial report language relevant to account planning.",
                        "recommended_action": "Validate the initiative with the account owner and map related offerings.",
                    },
                    {
                        "account_id": account_id,
                        "company_name": company_name,
                        "agent": AGENT_NAME,
                        "category": "financial",
                        "source_type": "annual_report",
                        "detected_at": detected_at,
                    },
                )
            )
    return signals[:6]


def analyze_financial_signals(
    company_name: str,
    account_id: str,
    annual_report_text: str,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Extract financial account intelligence signals."""
    detected_at = utc_now_iso()
    if not annual_report_text:
        return {"agent": AGENT_NAME, "status": "empty", "signals": []}

    payload = generate_json(_prompt(company_name, annual_report_text)) if use_llm else None
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
                    "category": "financial",
                    "source_type": "annual_report",
                    "detected_at": detected_at,
                    "confidence_score": 0.68,
                    "relevance_score": 70,
                },
            )
        )

    if not signals:
        signals = _fallback(company_name, account_id, annual_report_text, detected_at)

    return {"agent": AGENT_NAME, "status": "completed", "signals": signals}
