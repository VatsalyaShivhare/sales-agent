"""
Chat service — orchestrates the full pipeline:

  User message
    → memory read (get_user_memory tool)
    → agent loop (tool calls)
    → eval (self-scoring)
    → memory write
    → response
"""
import uuid
import logging
from sqlalchemy.orm import Session

from app.memory.factory import get_memory_backend
from app.agents.agent import run_agent
from app.services.eval_service import evaluate_response
from app.models.schemas import ChatResponse, EvalBlock

logger = logging.getLogger("chat_service")


def handle_chat(
    user_id: str,
    message: str,
    session_id: str | None,
    db: Session,
) -> ChatResponse:
    """
    Full pipeline for one user turn.
    """
    # Resolve or create session
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info("New session %s for user %s", session_id, user_id)
    else:
        logger.info("Continuing session %s for user %s", session_id, user_id)

    memory = get_memory_backend(db)

    # Persist the user's message
    memory.save_message(
        user_id=user_id,
        session_id=session_id,
        role="user",
        content=message,
    )

    # Run the agent (includes tool calls)
    assistant_response, tools_called, catalog_context, memory_context = run_agent(
        user_id=user_id,
        session_id=session_id,
        user_message=message,
        memory=memory,
    )

    # Self-eval
    eval_data = evaluate_response(
        user_message=message,
        assistant_response=assistant_response,
        catalog_context=catalog_context,
        memory_context=memory_context,
    )

    # Persist the assistant's response with eval
    memory.save_message(
        user_id=user_id,
        session_id=session_id,
        role="assistant",
        content=assistant_response,
        tools_called=tools_called,
        eval_data=eval_data,
    )

    logger.info(
        "Response for user=%s session=%s eval=%s flagged=%s",
        user_id,
        session_id,
        {k: v for k, v in eval_data.items() if k != "reasoning"},
        eval_data.get("flagged"),
    )

    return ChatResponse(
        response=assistant_response,
        eval=EvalBlock(**eval_data),
        tools_called=tools_called,
        session_id=session_id,
        user_id=user_id,
    )
