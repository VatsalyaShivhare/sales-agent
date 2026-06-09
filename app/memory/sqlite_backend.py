"""
SQLite-backed memory implementation.

Uses SQLAlchemy so it's trivially swappable to Postgres — just change
DATABASE_URL. The interface contract is defined in memory/base.py.
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.memory.base import MemoryBackend
from app.db.models import Message


class SQLiteMemoryBackend(MemoryBackend):

    def __init__(self, db: Session):
        self.db = db

    # ── Write ─────────────────────────────────────────────────────────────────

    def save_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        tools_called: Optional[list[str]] = None,
        eval_data: Optional[dict] = None,
    ) -> None:
        msg = Message(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            tools_called=",".join(tools_called) if tools_called else None,
        )
        if eval_data:
            msg.eval_groundedness = eval_data.get("groundedness")
            msg.eval_relevance = eval_data.get("relevance")
            msg.eval_confidence = eval_data.get("confidence")
            msg.eval_flagged = eval_data.get("flagged")
            msg.eval_reasoning = eval_data.get("reasoning")

        self.db.add(msg)
        self.db.commit()

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_history(self, user_id: str) -> list[dict]:
        rows = (
            self.db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.asc())
            .all()
        )
        return [r.to_dict() for r in rows]

    def get_recent_context(self, user_id: str, limit: int = 20) -> list[dict]:
        rows = (
            self.db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        return [r.to_dict() for r in reversed(rows)]  # restore chronological order

    def get_user_facts(self, user_id: str) -> str:
        """
        Build a compact memory summary from past assistant responses.
        
        Strategy: extract the last 30 user messages and assistant replies,
        then produce a bullet-point digest that the agent can inject as context.
        At scale this would be a vector search or a summarization model call.
        """
        rows = (
            self.db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.desc())
            .limit(30)
            .all()
        )
        if not rows:
            return "No prior memory for this user."

        # Format: "User asked: … / Agent responded: …"
        pairs = []
        rows_chrono = list(reversed(rows))
        for i, row in enumerate(rows_chrono):
            if row.role == "user":
                pairs.append(f"- User asked: {row.content[:200]}")
            else:
                pairs.append(f"  Agent said: {row.content[:200]}")

        summary_lines = pairs[-20:]  # keep most recent 20 lines to stay concise
        return "\n".join(summary_lines)

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_user(self, user_id: str) -> int:
        count = (
            self.db.query(Message)
            .filter(Message.user_id == user_id)
            .count()
        )
        self.db.query(Message).filter(Message.user_id == user_id).delete()
        self.db.commit()
        return count

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_eval_stats(self, user_id: str) -> dict:
        rows = (
            self.db.query(Message)
            .filter(
                Message.user_id == user_id,
                Message.role == "assistant",
                Message.eval_confidence.isnot(None),
            )
            .all()
        )
        if not rows:
            return {
                "total_assistant_responses": 0,
                "avg_groundedness": 0.0,
                "avg_relevance": 0.0,
                "avg_confidence": 0.0,
                "high_confidence_pct": 0.0,
                "flagged_count": 0,
                "flagged_pct": 0.0,
            }

        total = len(rows)
        avg_g = sum(r.eval_groundedness or 0 for r in rows) / total
        avg_r = sum(r.eval_relevance or 0 for r in rows) / total
        avg_c = sum(r.eval_confidence or 0 for r in rows) / total
        high = sum(1 for r in rows if (r.eval_confidence or 0) >= 0.8)
        flagged = sum(1 for r in rows if r.eval_flagged)

        return {
            "total_assistant_responses": total,
            "avg_groundedness": round(avg_g, 3),
            "avg_relevance": round(avg_r, 3),
            "avg_confidence": round(avg_c, 3),
            "high_confidence_pct": round(high / total * 100, 1),
            "flagged_count": flagged,
            "flagged_pct": round(flagged / total * 100, 1),
        }
