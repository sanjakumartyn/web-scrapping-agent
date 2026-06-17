"""Orchestrator to run all browser agents, then filter outputs with rules."""
import asyncio
from typing import Dict, List, Any
from layer1_agents.analysis_agents import run_signal_analysis
from layer1_agents.config.company_config import get_company_config
from layer1_agents.db.in_memory import save_signals as save_signals_in_memory
from layer1_agents.browser_agents.news_agent import collect_news
from layer1_agents.browser_agents.report_agent import collect_report
from layer1_agents.browser_agents.hiring_agent import collect_hiring
from layer1_agents.browser_agents.esg_agent import collect_esg
from layer1_agents.browser_agents.company_profile_agent import collect_company_profile
from layer1_agents.rule_engine.extractor import run_rule_engine


async def run_all_agents(company_name: str, account_id: str) -> Dict[str, Any]:
    """Run all four browser agents in parallel, then apply the rule engine.

    Args:
        company_name: Name of the company to research.
        account_id: Identifier for the account to tag signals with.

    Returns:
        A dictionary containing raw text from each source plus filtered signals.

    The function gathers agent results with return_exceptions=True so that a
    failure in one agent won't stop the others.
    """
    cfg = get_company_config(company_name)

    # Launch agents concurrently
    tasks = [
        collect_news(company_name),
        collect_report(company_name, cfg.get("investor_url")),
        collect_hiring(company_name),
        collect_esg(company_name, cfg.get("esg_url") or cfg.get("website")),
        collect_company_profile(company_name, cfg.get("website"), max_pages=2),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    sources = [
        (results[0], "news"),
        (results[1], "annual_report"),
        (results[2], "hiring"),
        (results[3], "esg"),
    ]
    company_profile = results[4] if len(results) > 4 else {}
    if isinstance(company_profile, Exception):
        print(f"Agent company_profile failed: {company_profile}")
        company_profile = {
            "company_name": company_name,
            "website": cfg.get("website"),
            "description": "",
            "products": [],
            "services": [],
            "brands": [],
            "industries_served": [],
            "business_segments": [],
            "source_urls": [],
            "confidence_score": 0.0,
        }

    source_outputs: List[Dict[str, Any]] = []
    raw_source_map: Dict[str, str] = {}
    rule_signals: List[Dict[str, Any]] = []

    for raw, source_type in sources:
        if isinstance(raw, Exception):
            print(f"Agent {source_type} failed: {raw}")
            raw_source_map[source_type] = ""
            source_outputs.append(
                {
                    "source_type": source_type,
                    "status": "failed",
                    "error": str(raw),
                    "content": "",
                }
            )
            continue

        print(f"Agent {source_type} returned: {len(raw) if raw else 0} chars")
        raw_text = raw or ""
        raw_source_map[source_type] = raw_text
        if not raw:
            # empty result: nothing to process
            print(f"Agent {source_type} returned empty, skipping")
        source_outputs.append(
            {
                "source_type": source_type,
                "status": "ok" if raw else "empty",
                "content": raw or "",
                "char_count": len(raw or ""),
            }
        )

        confirmed, _ambiguous = run_rule_engine(raw_text, source_type, account_id)
        if confirmed:
            rule_signals.extend(confirmed)

    account_intelligence = await run_signal_analysis(
        company_name=company_name,
        account_id=account_id,
        raw_sources=raw_source_map,
        company_profile=company_profile,
        rule_signals=rule_signals,
        timeout_seconds=20,
    )
    final_signals = account_intelligence.get("signals", [])
    if final_signals:
        save_signals_in_memory(final_signals, account_id)

    return {
        "account_id": account_id,
        "company_name": company_name,
        "status": "completed",
        "dashboard_ready": True,
        "signal_count": len(final_signals),
        "signals": final_signals,
        "account_intelligence": account_intelligence,
        "legacy_rule_signal_count": len(rule_signals),
        "legacy_rule_signals": rule_signals,
        "company_profile": company_profile,
        "sources": source_outputs,
    }


def trigger_agents(company_name: str, account_id: str) -> Dict[str, Any]:
    """Synchronous wrapper to run the async orchestrator from sync code.

    Uses asyncio.run to execute the async orchestration and returns raw details
    together with rule-engine filtered signals.
    """
    return asyncio.run(run_all_agents(company_name, account_id))
