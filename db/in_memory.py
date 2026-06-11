"""A simple in-memory store for signals (non-persistent).

Used when the user prefers printing results instead of persisting to MongoDB.
"""
from typing import List, Dict

# store mapping account_id -> list of signals
_STORE: Dict[str, List[Dict]] = {}


def save_signals(signals: List[Dict], account_id: str) -> None:
    """Save signals into the in-memory store under the account_id."""
    if not signals:
        return
    arr = _STORE.setdefault(account_id, [])
    arr.extend(signals)


def get_signals(account_id: str) -> List[Dict]:
    """Return signals for account_id from memory (empty list if none)."""
    return list(_STORE.get(account_id, []))
