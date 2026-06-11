"""MongoDB connection and helper functions for saving and retrieving signals."""
from typing import List, Dict
from datetime import datetime
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")


def _get_db():
    """Create and return a MongoDB database object."""
    try:
        client = MongoClient(MONGODB_URI)
        db = client["sales_intel"]
        return db
    except Exception as e:
        print(f"MongoDB connection error: {e}")
        return None


def save_signals(signals: List[Dict], account_id: str) -> None:
    """Insert a list of signal documents into the signals collection.

    Each document will be normalized to include required fields and
    a `created_at` timestamp. Errors are caught and printed.
    """
    db = _get_db()
    if not db:
        print("save_signals: no db connection available")
        return

    try:
        collection = db["signals"]
        to_insert = []
        for s in signals:
            doc = {
                "account_id": account_id,
                "signal_type": s.get("signal_type"),
                "description": s.get("description") or s.get("raw_snippet"),
                "confidence": float(s.get("confidence", 0.0)),
                "source_type": s.get("source_type"),
                "raw_snippet": s.get("raw_snippet"),
                "method": s.get("method", "rule_based"),
                "created_at": datetime.utcnow(),
            }
            to_insert.append(doc)

        if to_insert:
            collection.insert_many(to_insert)
    except Exception as e:
        print(f"Error saving signals: {e}")


def get_signals(account_id: str) -> List[Dict]:
    """Return all signals for a given account_id. Errors are caught.

    Args:
        account_id: Account identifier to filter signals.
    Returns:
        List of signal documents (possibly empty).
    """
    db = _get_db()
    if not db:
        print("get_signals: no db connection available")
        return []

    try:
        collection = db["signals"]
        results = list(collection.find({"account_id": account_id}))
        return results
    except Exception as e:
        print(f"Error fetching signals: {e}")
        return []


def signal_exists(account_id: str, signal_type: str) -> bool:
    """Check if a signal of the given type already exists for account.

    Args:
        account_id: Account identifier.
        signal_type: Type of signal to check for.
    Returns:
        True if such a signal exists, False otherwise.
    """
    db = _get_db()
    if not db:
        print("signal_exists: no db connection available")
        return False

    try:
        collection = db["signals"]
        exists = collection.count_documents({"account_id": account_id, "signal_type": signal_type}) > 0
        return exists
    except Exception as e:
        print(f"Error checking signal existence: {e}")
        return False
