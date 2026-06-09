"""
flag_for_human — escalation tool.

When the agent's confidence is low or the query is out-of-scope,
it can call this tool to log a flag that a human reviewer can query.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("flag_for_human")

# In-process log of flagged conversations (also persisted via eval_flagged in DB)
_FLAG_LOG: list[dict] = []


def flag_for_human(user_id: str, reason: str, session_id: Optional[str] = None) -> str:
    """
    Escalate a conversation to a human reviewer.
    
    Logs the flag with timestamp and reason. In production this would
    post to a webhook, Slack channel, or ticketing system.
    
    This is a registered LLM tool — called by the agent loop.
    """
    entry = {
        "user_id": user_id,
        "session_id": session_id,
        "reason": reason,
        "flagged_at": datetime.now(timezone.utc).isoformat(),
    }
    _FLAG_LOG.append(entry)
    logger.warning("FLAGGED FOR HUMAN REVIEW: %s", entry)

    return (
        f"Conversation flagged for human review. "
        f"Reason: {reason}. "
        f"A sales representative will follow up with {user_id} shortly."
    )


def get_flag_log() -> list[dict]:
    """Return all human-review flags (used by /admin/flags endpoint)."""
    return list(_FLAG_LOG)
