"""Sentence splitting and scoring functions for the rule engine."""
import re
from typing import List, Tuple, Dict
from layer1_agents.rule_engine.signal_rules import SIGNAL_RULES, SOURCE_BOOST, THRESHOLDS


def split_sentences(text: str) -> List[str]:
    """Split text into sentences, clean whitespace, and filter short ones.

    Sentences shorter than 30 characters are discarded.
    """
    if not text:
        return []

    cleaned = re.sub(r"\s+", " ", text).strip()

    # Naive sentence split on punctuation followed by space and capital letter
    parts = re.split(r'(?<=[.!?\n])\s+', cleaned)
    sentences = [p.strip() for p in parts if len(p.strip()) > 30]
    return sentences


def score_sentence(sentence: str, signal_type: str) -> float:
    """Score a single sentence for a given signal type using keyword hits.

    Scoring formula:
      - base 0.50 if any primary hits exist
      - add up to 0.35 from primary hits (0.15 per hit)
      - add up to 0.15 from secondary hits (0.05 per hit)
      - cap score at 0.95

    Returns rounded score to 2 decimals.
    """
    if not sentence:
        return 0.0

    s = sentence.lower()
    rules = SIGNAL_RULES.get(signal_type, {})
    primaries = rules.get("primary", [])
    secondaries = rules.get("secondary", [])

    primary_hits = sum(1 for kw in primaries if kw in s)
    if primary_hits == 0:
        return 0.0

    secondary_hits = sum(1 for kw in secondaries if kw in s)

    score = 0.50
    score += min(primary_hits * 0.15, 0.35)
    score += min(secondary_hits * 0.05, 0.15)
    score = min(score, 0.95)
    return round(score, 2)


def run_rule_engine(raw_text: str, source_type: str, account_id: str) -> Tuple[List[Dict], List[Dict]]:
    """Run the rule engine on raw text to produce confirmed and ambiguous signals.

    Returns a tuple: (confirmed_list, ambiguous_list). Each item is a dict with
    account_id, signal_type, description, confidence, source_type, raw_snippet.

    Handles empty input gracefully by returning two empty lists.
    """
    confirmed = []
    ambiguous = []

    if not raw_text:
        return confirmed, ambiguous

    sentences = split_sentences(raw_text)
    print(f"  [extractor] source_type={source_type}, sentences extracted={len(sentences)}")
    if sentences:
        print(f"  [extractor] first sentence sample: {sentences[0][:100]}")
    
    boost = SOURCE_BOOST.get(source_type, 0.0)

    for sent in sentences:
        for signal_type in SIGNAL_RULES.keys():
            base_score = score_sentence(sent, signal_type)
            if base_score == 0.0:
                continue
            print(f"  [extractor] MATCH! signal_type={signal_type}, base_score={base_score}, sent={sent[:80]}")

            final = round(min(base_score + boost, 0.95), 2)

            item = {
                "account_id": account_id,
                "signal_type": signal_type,
                "description": sent,
                "confidence": final,
                "source_type": source_type,
                "raw_snippet": sent,
                "method": "rule_based",
            }

            if final >= THRESHOLDS["HIGH"]:
                confirmed.append(item)
            elif THRESHOLDS["LOW"] <= final < THRESHOLDS["HIGH"]:
                ambiguous.append(item)
            # else discard silently

    return confirmed, ambiguous
