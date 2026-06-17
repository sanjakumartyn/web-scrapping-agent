"""Hiring signal analysis agent."""

from __future__ import annotations

from typing import Any, Dict, List

from .llm_client import generate_json
from .signal_utils import keyword_relevance, matching_sentences, normalize_signal, trim_text, utc_now_iso


AGENT_NAME = "hiring_signal_agent"
ALLOWED_TYPES = ["role_category_demand", "workforce_expansion", "capability_buildout"]
ROLE_MAPPINGS = [
    (
        "sustainability_esg",
        ["sustainability", "esg", "environment", "ehs", "carbon", "renewable", "csr"],
        "ESG-aligned materials, sustainability services, compliance, and reporting solutions",
    ),
    (
        "digital_data",
        ["data", "analytics", "digital", "automation", "cloud", "erp", "sap", "ai", "machine learning"],
        "digital transformation, automation, analytics, cloud, and enterprise software solutions",
    ),
    (
        "supply_chain_procurement",
        ["supply", "procurement", "sourcing", "vendor", "logistics", "warehouse", "purchase"],
        "supply chain optimization, sourcing, logistics, and procurement solutions",
    ),
    (
        "manufacturing_engineering",
        ["manufacturing", "production", "plant", "maintenance", "quality", "process", "engineer"],
        "manufacturing expansion, plant operations, industrial equipment, and quality solutions",
    ),
    (
        "commercial_expansion",
        ["sales", "business development", "marketing", "territory", "channel", "key account"],
        "go-to-market, channel expansion, sales enablement, and customer growth solutions",
    ),
]


def map_role_to_solution_area(text: str) -> Dict[str, str]:
    lowered = (text or "").lower()
    for role_category, keywords, solution_area in ROLE_MAPPINGS:
        if any(keyword in lowered for keyword in keywords):
            return {"role_category": role_category, "solution_area": solution_area}
    return {
        "role_category": "general_hiring",
        "solution_area": "general workforce growth and operating capacity solutions",
    }


def _prompt(company_name: str, hiring_text: str) -> str:
    return f"""
You are the hiring signal agent for B2B account intelligence.
Analyze job postings and hiring mentions for {company_name}. Map role categories to internal solution areas.

Use these mappings when relevant:
- sustainability/ESG/EHS roles -> ESG-aligned materials, sustainability services, compliance, reporting
- digital/data/cloud/ERP/automation roles -> digital transformation, automation, analytics, cloud, enterprise software
- supply/procurement/logistics roles -> supply chain optimization, sourcing, logistics, procurement
- plant/production/maintenance/quality/engineering roles -> manufacturing expansion, plant operations, industrial equipment
- sales/marketing/channel roles -> commercial expansion and go-to-market solutions

Return JSON only:
{{
  "signals": [
    {{
      "signal_type": "role_category_demand|workforce_expansion|capability_buildout",
      "classification": "opportunity|monitor",
      "title": "short hiring signal title",
      "description": "what roles imply about business need",
      "evidence": "job title or posting evidence",
      "source_date": "YYYY-MM-DD or null",
      "role_category": "mapped category",
      "solution_area": "mapped internal solution area",
      "confidence_score": 0.0,
      "recency_score": 0,
      "relevance_score": 0,
      "reasoning": "why this hiring implies demand",
      "recommended_action": "next action"
    }}
  ]
}}

Rules:
- Maximum 6 signals.
- Group similar job titles instead of returning duplicates.
- Do not invent roles.

Hiring text:
{trim_text(hiring_text, 35000)}
""".strip()


def _fallback(company_name: str, account_id: str, hiring_text: str, detected_at: str) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    all_keywords = [keyword for _, keywords, _ in ROLE_MAPPINGS for keyword in keywords] + ["hiring", "job", "opening"]
    for sentence in matching_sentences(hiring_text, all_keywords, limit=8):
        mapped = map_role_to_solution_area(sentence)
        signals.append(
            normalize_signal(
                {
                    "signal_type": "role_category_demand",
                    "title": f"{mapped['role_category'].replace('_', ' ').title()} hiring signal",
                    "description": sentence,
                    "evidence": sentence,
                    "role_category": mapped["role_category"],
                    "solution_area": mapped["solution_area"],
                    "confidence_score": 0.62,
                    "relevance_score": keyword_relevance(sentence, all_keywords, base=64),
                    "reasoning": "Role category suggests an active capability buildout.",
                    "recommended_action": "Align relevant solution proof points to the hiring category.",
                },
                {
                    "account_id": account_id,
                    "company_name": company_name,
                    "agent": AGENT_NAME,
                    "category": "hiring",
                    "source_type": "hiring",
                    "detected_at": detected_at,
                },
            )
        )
    return signals[:6]


def analyze_hiring_signals(
    company_name: str,
    account_id: str,
    hiring_text: str,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Extract hiring signals and map role categories to solution areas."""
    detected_at = utc_now_iso()
    if not hiring_text:
        return {"agent": AGENT_NAME, "status": "empty", "signals": []}

    payload = generate_json(_prompt(company_name, hiring_text)) if use_llm else None
    raw_signals = payload.get("signals", []) if isinstance(payload, dict) else []
    signals: List[Dict[str, Any]] = []

    for raw in raw_signals:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("signal_type", "")).lower() not in ALLOWED_TYPES:
            continue
        mapped = map_role_to_solution_area(
            " ".join([str(raw.get("role_category", "")), str(raw.get("evidence", "")), str(raw.get("description", ""))])
        )
        raw.setdefault("role_category", mapped["role_category"])
        raw.setdefault("solution_area", mapped["solution_area"])
        signals.append(
            normalize_signal(
                raw,
                {
                    "account_id": account_id,
                    "company_name": company_name,
                    "agent": AGENT_NAME,
                    "category": "hiring",
                    "source_type": "hiring",
                    "detected_at": detected_at,
                    "confidence_score": 0.68,
                    "relevance_score": 68,
                },
            )
        )

    if not signals:
        signals = _fallback(company_name, account_id, hiring_text, detected_at)

    return {"agent": AGENT_NAME, "status": "completed", "signals": signals}
