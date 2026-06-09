"""
get_user_memory — retrieves a user's past conversation context.

Called by the agent to inject prior session facts before generating
a response. This is a real DB query, not string injection.
"""
from app.memory.base import MemoryBackend


def get_user_memory(user_id: str, memory: MemoryBackend) -> str:
    """
    Retrieve a summary of past interactions and known facts about this user.
    
    Returns a formatted string describing what the agent already knows,
    so it can continue conversations seamlessly across sessions.
    
    This is a registered LLM tool — called by the agent loop.
    """
    facts = memory.get_user_facts(user_id)
    if facts == "No prior memory for this user.":
        return "This is the user's first interaction. No prior context available."

    return (
        f"[Memory for user '{user_id}']\n"
        f"Prior conversation context (most recent first):\n"
        f"{facts}\n"
        f"[End of memory context]"
    )
