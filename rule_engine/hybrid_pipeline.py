"""Hybrid pipeline combining rule engine results with LLM verification."""
from typing import List, Dict
from layer1_agents.rule_engine.extractor import run_rule_engine
from layer1_agents.llm_verify.verifier import llm_verify
from layer1_agents.db.in_memory import save_signals as save_signals_in_memory


def run_hybrid_pipeline(raw_text: str, source_type: str, account_id: str) -> List[Dict]:
    """Run rule engine, verify ambiguous signals with LLM, save confirmed.

    Returns the list of confirmed signals saved.
    """
    confirmed, ambiguous = run_rule_engine(raw_text, source_type, account_id)
    print(f"run_hybrid_pipeline: confirmed={len(confirmed)} ambiguous={len(ambiguous)}")

    for amb in ambiguous:
        verified = llm_verify(amb)
        if verified:
            confirmed.append(verified)

    # Print confirmed signals and store in-memory (non-persistent) for inspection.
    if confirmed:
        print(f"run_hybrid_pipeline: saving/printing {len(confirmed)} confirmed signals for {account_id}")
        for s in confirmed:
            print(s)
        try:
            save_signals_in_memory(confirmed, account_id)
        except Exception as e:
            print(f"run_hybrid_pipeline: in-memory save error: {e}")

    return confirmed
