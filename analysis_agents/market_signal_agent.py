"""Market signal analysis agent."""

from __future__ import annotations

from typing import Any, Dict, List

from .llm_client import generate_json
from .signal_utils import keyword_relevance, matching_sentences, normalize_signal, trim_text, utc_now_iso


AGENT_NAME = "market_signal_agent"
ALLOWED_TYPES = [
    "plant_expansion",
    "digital_transformation",
    "supply_chain_diversification",
    "sustainability_pledge",
    "demand_trigger",
]
KEYWORDS = {
    "plant_expansion": [
        "new plant",
        "plant expansion",
        "capacity expansion",
        "new factory",
        "greenfield",
        "brownfield",
        "manufacturing expansion",
    ],
    "digital_transformation": [
        "digital transformation",
        "automation",
        "erp",
        "cloud",
        "data analytics",
        "artificial intelligence",
        "industry 4.0",
        "iot",
    ],
    "supply_chain_diversification": [
        "supplier diversification",
        "supply chain",
        "local sourcing",
        "import substitution",
        "vendor",
        "procurement",
        "logistics",
    ],
    "sustainability_pledge": [
        "net zero",
        "renewable energy",
        "carbon neutral",
        "emissions",
        "sustainability target",
        "decarbonization",
        "circular economy",
    ],
}


def _prompt(company_name: str, market_text: str) -> str:
    return f"""
You are the market signal agent for B2B account intelligence.
Identify demand triggers for {company_name} from news, ESG, annual report, and public website text.

Signal types allowed:
- plant_expansion
- digital_transformation
- supply_chain_diversification
- sustainability_pledge
- demand_trigger

Return JSON only:
{{
  "signals": [
    {{
      "signal_type": "plant_expansion|digital_transformation|supply_chain_diversification|sustainability_pledge|demand_trigger",
      "classification": "opportunity|risk|monitor",
      "title": "short trigger title",
      "description": "what changed and why it creates demand",
      "evidence": "short source evidence",
      "source_date": "YYYY-MM-DD or null",
      "demand_trigger": "expansion|digital|supply_chain|sustainability|other",
      "confidence_score": 0.0,
      "recency_score": 0,
      "relevance_score": 0,
      "reasoning": "why this indicates demand",
      "recommended_action": "next action"
    }}
  ]
}}

Rules:
- Maximum 8 signals.
- Prefer concrete initiatives over generic brand statements.
- Do not invent dates, places, suppliers, or initiatives.
- Score relevance by likely near-term B2B sales usefulness.

Source text:
{trim_text(market_text, 50000)}
""".strip()


def _fallback(company_name: str, account_id: str, market_text: str, detected_at: str) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    for signal_type, keywords in KEYWORDS.items():
        for sentence in matching_sentences(market_text, keywords, limit=2):
            trigger = {
                "plant_expansion": "expansion",
                "digital_transformation": "digital",
                "supply_chain_diversification": "supply_chain",
                "sustainability_pledge": "sustainability",
            }[signal_type]
            signals.append(
                normalize_signal(
                    {
                        "signal_type": signal_type,
                        "title": sentence[:95],
                        "description": sentence,
                        "evidence": sentence,
                        "demand_trigger": trigger,
                        "confidence_score": 0.62,
                        "relevance_score": keyword_relevance(sentence, keywords, base=68),
                        "reasoning": "Matched market trigger language relevant to demand creation.",
                        "recommended_action": "Map the trigger to current offerings and confirm timing with the account.",
                    },
                    {
                        "account_id": account_id,
                        "company_name": company_name,
                        "agent": AGENT_NAME,
                        "category": "market",
                        "source_type": "public_mentions",
                        "detected_at": detected_at,
                    },
                )
            )
    return signals[:8]


def analyze_market_signals(
    company_name: str,
    account_id: str,
    raw_sources: Dict[str, str],
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Extract market demand trigger signals."""
    detected_at = utc_now_iso()
    market_text = "\n\n".join(
        [
            raw_sources.get("news", ""),
            raw_sources.get("annual_report", ""),
            raw_sources.get("esg", ""),
        ]
    )
    if not market_text.strip():
        return {"agent": AGENT_NAME, "status": "empty", "signals": []}

    payload = generate_json(_prompt(company_name, market_text)) if use_llm else None
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
                    "category": "market",
                    "source_type": "public_mentions",
                    "detected_at": detected_at,
                    "confidence_score": 0.68,
                    "relevance_score": 72,
                },
            )
        )

    if not signals:
        signals = _fallback(company_name, account_id, market_text, detected_at)

    return {"agent": AGENT_NAME, "status": "completed", "signals": signals}
