"""
ORM models.  One table (messages) handles all storage needs —
sessions are logical groupings identified by session_id UUID.
"""
import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime
from app.db.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    session_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)          # "user" | "assistant"
    content = Column(Text, nullable=False)

    # Eval fields (populated for assistant messages only)
    eval_groundedness = Column(Float, nullable=True)
    eval_relevance = Column(Float, nullable=True)
    eval_confidence = Column(Float, nullable=True)
    eval_flagged = Column(Boolean, nullable=True)
    eval_reasoning = Column(Text, nullable=True)

    # Comma-separated tool names, e.g. "search_catalog,get_user_memory"
    tools_called = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def tools_list(self) -> list[str]:
        if not self.tools_called:
            return []
        return [t.strip() for t in self.tools_called.split(",") if t.strip()]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "eval": {
                "groundedness": self.eval_groundedness,
                "relevance": self.eval_relevance,
                "confidence": self.eval_confidence,
                "flagged": self.eval_flagged,
                "reasoning": self.eval_reasoning,
            } if self.eval_groundedness is not None else None,
            "tools_called": self.tools_list(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
