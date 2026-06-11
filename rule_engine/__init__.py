"""Rule engine package for signal extraction and hybrid pipeline."""

from .signal_rules import SIGNAL_RULES, SOURCE_BOOST, THRESHOLDS
from .extractor import run_rule_engine, split_sentences, score_sentence
from .hybrid_pipeline import run_hybrid_pipeline

__all__ = [
    "SIGNAL_RULES",
    "SOURCE_BOOST",
    "THRESHOLDS",
    "run_rule_engine",
    "run_hybrid_pipeline",
]
