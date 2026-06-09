from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


# ─── Request / Response Schemas ───────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="User's message")
    session_id: Optional[str] = Field(
        default=None,
        description="Existing session ID to continue. If omitted, a new session is created.",
    )


class EvalBlock(BaseModel):
    groundedness: float = Field(..., ge=0.0, le=1.0)
    relevance: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    flagged: bool
    reasoning: str


class ChatResponse(BaseModel):
    response: str
    eval: EvalBlock
    tools_called: list[str]
    session_id: str
    user_id: str


# ─── History Schemas ───────────────────────────────────────────────────────────

class MessageRecord(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    tools_called: Optional[list[str]] = None
    eval: Optional[EvalBlock] = None
    created_at: datetime

    class Config:
        from_attributes = True


class HistoryResponse(BaseModel):
    user_id: str
    total_messages: int
    sessions: list[str]
    messages: list[MessageRecord]


# ─── Eval Summary Schema ───────────────────────────────────────────────────────

class EvalSummaryResponse(BaseModel):
    user_id: str
    total_assistant_responses: int
    avg_groundedness: float
    avg_relevance: float
    avg_confidence: float
    high_confidence_pct: float   # % with confidence >= 0.8
    flagged_count: int
    flagged_pct: float


# ─── Catalog Schema ───────────────────────────────────────────────────────────

class CatalogResponse(BaseModel):
    catalog: dict


# ─── Health Schema ────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    db: str


# ─── Memory Delete Schema ─────────────────────────────────────────────────────

class MemoryDeleteResponse(BaseModel):
    user_id: str
    deleted_messages: int
    status: str
