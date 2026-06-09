"""
Abstract base class for the memory layer.

Swapping backends (SQLite → Postgres → Mem0 → Redis) means implementing
this interface in a new file and changing the import in memory/factory.py.
Nothing else changes.
"""
from abc import ABC, abstractmethod
from typing import Optional


class MemoryBackend(ABC):

    @abstractmethod
    def save_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        tools_called: Optional[list[str]] = None,
        eval_data: Optional[dict] = None,
    ) -> None:
        """Persist a single message turn."""

    @abstractmethod
    def get_history(self, user_id: str) -> list[dict]:
        """Return all messages for a user across all sessions, oldest first."""

    @abstractmethod
    def get_recent_context(self, user_id: str, limit: int = 20) -> list[dict]:
        """
        Return the N most-recent messages for a user (both roles).
        Used to build the LLM context window.
        """

    @abstractmethod
    def get_user_facts(self, user_id: str) -> str:
        """
        Return a compact summary of known user interests / facts.
        Used by the get_user_memory tool.
        """

    @abstractmethod
    def delete_user(self, user_id: str) -> int:
        """Delete all memory for a user. Returns number of deleted rows."""

    @abstractmethod
    def get_eval_stats(self, user_id: str) -> dict:
        """Return aggregated eval statistics for a user."""
