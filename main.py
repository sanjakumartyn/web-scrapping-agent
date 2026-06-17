"""FastAPI entry point exposing endpoints to trigger analysis and fetch raw details."""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from layer1_agents.db.in_memory import get_signals
from layer1_agents.browser_agents.orchestrator import trigger_agents
from layer1_agents.services.signal_processor import process_signals

app = FastAPI()


class AnalyseRequest(BaseModel):
    company_name: str
    account_id: str


@app.post("/analyse/", include_in_schema=False)
@app.post("/analyse")
def analyse(req: AnalyseRequest) -> Dict[str, Any]:
    """Run agent collectors synchronously and return raw source details.

    Triggers the browser agents and returns the raw text gathered from each
    source without applying rule-engine filtering.
    """
    try:
        print(f"analyse: starting agent run for {req.company_name} (account: {req.account_id})")
        result = trigger_agents(req.company_name, req.account_id)
        source_count = len(result.get("sources", [])) if isinstance(result, dict) else 0
        print(f"analyse: collected raw details from {source_count} sources")
        if isinstance(result, dict):
            if result.get("dashboard_ready") and result.get("account_intelligence"):
                result["signal_count"] = len(result.get("signals", []))
                result["raw_signal_count"] = result.get(
                    "legacy_rule_signal_count",
                    len(result.get("legacy_rule_signals", [])),
                )
                return result

            raw_signals = result.get("signals", [])
            cleaned_signals = process_signals([
                {
                    "account_id": result.get("account_id", req.account_id),
                    "company_name": result.get("company_name", req.company_name),
                    "signals": raw_signals,
                }
            ])
            result["signals"] = cleaned_signals
            result["signal_count"] = len(cleaned_signals)
            result["raw_signal_count"] = len(raw_signals)
            return result

        return {
            "company_name": req.company_name,
            "account_id": req.account_id,
            "status": "completed",
            "sources": [],
        }
    except Exception as e:
        print(f"analyse endpoint error: {e}")
        return {"error": str(e), "status": "failed"}


@app.get("/signals/{account_id}")
def signals(account_id: str) -> List[Dict]:
    """Retrieve all saved signals for the given account_id from MongoDB."""
    try:
        # Return non-persistent in-memory signals collected during the run.
        return get_signals(account_id)
    except Exception as e:
        print(f"signals endpoint error: {e}")
        return []


@app.get("/health")
def health() -> Dict[str, str]:
    """Health endpoint for readiness checks."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)
