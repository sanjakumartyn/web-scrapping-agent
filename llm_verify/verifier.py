"""LLM-based verification using Google Gemini to validate ambiguous signals."""
import os
import json
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)


def llm_verify(signal: Dict) -> Optional[Dict]:
    """Ask gpt-4o-mini whether a sentence indicates a useful business signal.

    Expects `signal` to include 'signal_type' and 'raw_snippet'. Calls the LLM
    and expects a JSON response like: {"is_signal": bool, "confidence": float, "reason": str}

    If the LLM confirms with confidence >= 0.60, the signal dict is updated
    with `method` and `llm_reason` and returned. On any error or low confidence
    returns None.
    """
    try:
        prompt = (
            f"Does this sentence indicate a {signal.get('signal_type')} business signal "
            f"useful for a B2B sales team? Sentence: {signal.get('raw_snippet')}\n"
            'Reply ONLY with JSON: {"is_signal": bool, "confidence": float, "reason": str}'
        )

        model = genai.GenerativeModel('gemini-1.5-pro')
        resp = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0,
                max_output_tokens=80,
            )
        )

        text = resp.text
        parsed = json.loads(text)

        is_signal = bool(parsed.get("is_signal", False))
        confidence = float(parsed.get("confidence", 0.0))
        reason = parsed.get("reason", "")

        if is_signal and confidence >= 0.60:
            signal["method"] = "llm_verified"
            signal["llm_reason"] = reason
            signal["confidence"] = round(confidence, 2)
            return signal
        return None
    except Exception as e:
        print(f"llm_verify error: {e}")
        return None
