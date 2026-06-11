"""Orchestrator to run all browser agents, then filter outputs with rules."""
import asyncio
from typing import Dict, List, Any
from layer1_agents.rule_engine.hybrid_pipeline import run_hybrid_pipeline
from layer1_agents.config.company_config import get_company_config
from layer1_agents.browser_agents.news_agent import collect_news
from layer1_agents.browser_agents.report_agent import collect_report
from layer1_agents.browser_agents.hiring_agent import collect_hiring
from layer1_agents.browser_agents.esg_agent import collect_esg


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
        collect_esg(company_name, cfg.get("website")),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    sources = [
        (results[0], "news"),
        (results[1], "annual_report"),
        (results[2], "hiring"),
        (results[3], "esg"),
    ]

    source_outputs: List[Dict[str, Any]] = []
    all_signals: List[Dict[str, Any]] = []

    for raw, source_type in sources:
        if isinstance(raw, Exception):
            print(f"Agent {source_type} failed: {raw}")
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

        confirmed = run_hybrid_pipeline(raw, source_type, account_id)
        if confirmed:
            all_signals.extend(confirmed)

    return {
        "account_id": account_id,
        "company_name": company_name,
        "status": "completed",
        "signal_count": len(all_signals),
        "signals": all_signals,
        "sources": source_outputs,
    }


def trigger_agents(company_name: str, account_id: str) -> Dict[str, Any]:
    """Synchronous wrapper to run the async orchestrator from sync code.

    Uses asyncio.run to execute the async orchestration and returns raw details
    together with rule-engine filtered signals.
    """
    return asyncio.run(run_all_agents(company_name, account_id))
