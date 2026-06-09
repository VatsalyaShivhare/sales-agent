"""
API route handlers — thin layer, no business logic here.
All logic lives in services/.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    HistoryResponse,
    MemoryDeleteResponse,
    CatalogResponse,
    HealthResponse,
    EvalSummaryResponse,
    MessageRecord,
    EvalBlock,
)
from app.services.chat_service import handle_chat
from app.memory.factory import get_memory_backend
from app.tools.catalog_tool import get_full_catalog
from app.tools.flag_tool import get_flag_log
from app.db.database import engine

router = APIRouter()


# ─── POST /chat/{user_id} ─────────────────────────────────────────────────────

@router.post(
    "/chat/{user_id}",
    response_model=ChatResponse,
    summary="Send a message to the sales assistant",
    tags=["Chat"],
)
def chat(user_id: str, body: ChatRequest, db: Session = Depends(get_db)):
    """
    Send a message and receive a response with self-eval scores.
    Pass `session_id` to continue an existing conversation; omit to start a new one.
    """
    return handle_chat(
        user_id=user_id,
        message=body.message,
        session_id=body.session_id,
        db=db,
    )


# ─── GET /chat/{user_id}/history ─────────────────────────────────────────────

@router.get(
    "/chat/{user_id}/history",
    response_model=HistoryResponse,
    summary="Full conversation history across all sessions",
    tags=["Chat"],
)
def get_history(user_id: str, db: Session = Depends(get_db)):
    memory = get_memory_backend(db)
    raw = memory.get_history(user_id)

    messages = []
    for m in raw:
        eval_block = None
        if m.get("eval") and m["eval"].get("groundedness") is not None:
            eval_block = EvalBlock(**m["eval"])
        messages.append(
            MessageRecord(
                id=m["id"],
                session_id=m["session_id"],
                role=m["role"],
                content=m["content"],
                tools_called=m.get("tools_called"),
                eval=eval_block,
                created_at=m["created_at"],
            )
        )

    sessions = list(dict.fromkeys(m.session_id for m in messages))

    return HistoryResponse(
        user_id=user_id,
        total_messages=len(messages),
        sessions=sessions,
        messages=messages,
    )


# ─── DELETE /chat/{user_id}/memory ───────────────────────────────────────────

@router.delete(
    "/chat/{user_id}/memory",
    response_model=MemoryDeleteResponse,
    summary="Wipe all memory for a user (GDPR reset)",
    tags=["Chat"],
)
def delete_memory(user_id: str, db: Session = Depends(get_db)):
    memory = get_memory_backend(db)
    deleted = memory.delete_user(user_id)
    return MemoryDeleteResponse(
        user_id=user_id,
        deleted_messages=deleted,
        status="deleted",
    )


# ─── GET /chat/{user_id}/evals ────────────────────────────────────────────────

@router.get(
    "/chat/{user_id}/evals",
    response_model=EvalSummaryResponse,
    summary="Aggregated eval scores across all sessions",
    tags=["Chat"],
)
def get_evals(user_id: str, db: Session = Depends(get_db)):
    memory = get_memory_backend(db)
    stats = memory.get_eval_stats(user_id)
    return EvalSummaryResponse(user_id=user_id, **stats)


# ─── GET /catalog ─────────────────────────────────────────────────────────────

@router.get(
    "/catalog",
    response_model=CatalogResponse,
    summary="Product and pricing catalog",
    tags=["Catalog"],
)
def get_catalog():
    return CatalogResponse(catalog=get_full_catalog())


# ─── GET /health ──────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    tags=["System"],
)
def health(db: Session = Depends(get_db)):
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    return HealthResponse(status="ok", version="1.0.0", db=db_status)


# ─── GET /admin/flags (bonus) ────────────────────────────────────────────────

@router.get(
    "/admin/flags",
    summary="Human-review flag log",
    tags=["Admin"],
)
def get_flags():
    """Returns all conversations flagged for human review."""
    return {"flags": get_flag_log()}
