"""
Eval service — self-scores every assistant response using Groq (OpenAI-compatible SDK).
"""
import json
import re
import logging
import os
from openai import OpenAI

logger = logging.getLogger("eval_service")

_CLIENT = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY", ""),
    base_url="https://api.groq.com/openai/v1",
)
_MODEL = "llama-3.1-8b-instant"

EVAL_SYSTEM = """You are a strict quality-assurance evaluator for an AI sales assistant.
Score the assistant response on three dimensions (0.0-1.0 floats):
- groundedness: grounded in provided catalog context (1.0=fully grounded, 0.0=hallucinated)
- relevance: how relevant to the user's question (1.0=perfect, 0.0=off-topic)
- confidence: overall confidence the response is accurate and helpful

Set flagged=true if ANY: confidence<0.65, info not in catalog, out-of-scope question, misleading response.

Respond ONLY with valid JSON, no markdown:
{"groundedness": 0.0, "relevance": 0.0, "confidence": 0.0, "flagged": false, "reasoning": "one sentence"}"""


def evaluate_response(
    user_message: str,
    assistant_response: str,
    catalog_context: str,
    memory_context: str,
) -> dict:
    eval_input = (
        f"USER QUESTION:\n{user_message}\n\n"
        f"CATALOG CONTEXT:\n{catalog_context or 'none'}\n\n"
        f"MEMORY CONTEXT:\n{memory_context or 'none'}\n\n"
        f"ASSISTANT RESPONSE:\n{assistant_response}"
    )

    try:
        response = _CLIENT.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": EVAL_SYSTEM},
                {"role": "user", "content": eval_input},
            ],
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)

        return {
            "groundedness": round(float(data.get("groundedness", 0.5)), 3),
            "relevance": round(float(data.get("relevance", 0.5)), 3),
            "confidence": round(float(data.get("confidence", 0.5)), 3),
            "flagged": bool(data.get("flagged", False)),
            "reasoning": str(data.get("reasoning", "Eval completed.")),
        }

    except Exception as exc:
        logger.error("Eval failed: %s", exc)
        return {
            "groundedness": 0.5,
            "relevance": 0.5,
            "confidence": 0.5,
            "flagged": True,
            "reasoning": f"Eval failed — conservative scores. Error: {exc}",
        }