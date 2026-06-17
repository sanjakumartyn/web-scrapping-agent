"""Account intelligence summary generation."""

from __future__ import annotations

from typing import Any, Dict, List

from .llm_client import generate_json
from .signal_utils import trim_text, utc_now_iso


def _fallback_summary(company_name: str, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    top = sorted(signals, key=lambda item: item.get("priority_score", 0), reverse=True)[:5]
    top_titles = [signal.get("title", "") for signal in top if signal.get("title")]
    triggers = list(dict.fromkeys(signal.get("demand_trigger") for signal in signals if signal.get("demand_trigger")))[:5]
    solution_areas = list(dict.fromkeys(signal.get("solution_area") for signal in signals if signal.get("solution_area")))[:5]
    risks = [
        signal.get("title", "")
        for signal in signals
        if str(signal.get("classification", "")).lower() == "risk" and signal.get("title")
    ][:3]

    if top_titles:
        executive_summary = f"{company_name} shows {len(signals)} account signals led by: " + "; ".join(top_titles[:3])
    else:
        executive_summary = f"No high-confidence account intelligence signals were generated for {company_name}."

    return {
        "executive_summary": executive_summary,
        "top_opportunities": top_titles,
        "buying_triggers": triggers,
        "solution_areas": solution_areas,
        "risk_flags": risks,
        "recommended_next_actions": [
            "Prioritize the highest priority signals for account qualification.",
            "Validate timing, owners, and budget with public filings or account conversations.",
            "Map solution proof points to the detected trigger and role category.",
        ]
        if signals
        else [],
        "generated_at": utc_now_iso(),
        "method": "fallback",
    }


def generate_account_summary(
    company_name: str,
    signals: List[Dict[str, Any]],
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Generate a compact account intelligence summary."""
    if not signals:
        return _fallback_summary(company_name, signals)

    compact_signals = [
        {
            "category": signal.get("category"),
            "signal_type": signal.get("signal_type"),
            "title": signal.get("title"),
            "description": signal.get("description"),
            "priority_score": signal.get("priority_score"),
            "demand_trigger": signal.get("demand_trigger"),
            "solution_area": signal.get("solution_area"),
            "classification": signal.get("classification"),
        }
        for signal in sorted(signals, key=lambda item: item.get("priority_score", 0), reverse=True)[:12]
    ]

    prompt = f"""
You are generating an account intelligence dashboard summary for {company_name}.
Use only the supplied signals.

Return JSON only:
{{
  "executive_summary": "3-5 sentence account intelligence summary",
  "top_opportunities": ["short opportunity"],
  "buying_triggers": ["short trigger"],
  "solution_areas": ["solution area"],
  "risk_flags": ["risk or monitor item"],
  "recommended_next_actions": ["specific next action"]
}}

Signals:
{trim_text(str(compact_signals), 18000)}
""".strip()

    payload = generate_json(prompt, max_output_tokens=1200) if use_llm else None
    if not isinstance(payload, dict):
        return _fallback_summary(company_name, signals)

    summary = {
        "executive_summary": str(payload.get("executive_summary") or "").strip(),
        "top_opportunities": payload.get("top_opportunities") if isinstance(payload.get("top_opportunities"), list) else [],
        "buying_triggers": payload.get("buying_triggers") if isinstance(payload.get("buying_triggers"), list) else [],
        "solution_areas": payload.get("solution_areas") if isinstance(payload.get("solution_areas"), list) else [],
        "risk_flags": payload.get("risk_flags") if isinstance(payload.get("risk_flags"), list) else [],
        "recommended_next_actions": payload.get("recommended_next_actions")
        if isinstance(payload.get("recommended_next_actions"), list)
        else [],
        "generated_at": utc_now_iso(),
        "method": "llm",
    }

    if not summary["executive_summary"]:
        return _fallback_summary(company_name, signals)
    return summary
