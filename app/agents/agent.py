import json
import logging
import os
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from app.memory.base import MemoryBackend
from app.tools.catalog_tool import search_catalog
from app.tools.memory_tool import get_user_memory
from app.tools.flag_tool import flag_for_human

logger = logging.getLogger("agent")   # ← must be here, at module level

_CLIENT = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)
_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are Alex, a knowledgeable and friendly sales assistant for NexusHQ — a B2B SaaS operations platform.

Your role:
- Help prospects understand NexusHQ's plans, pricing, and features
- Answer questions accurately using the search_catalog tool
- Remember returning users using the get_user_memory tool
- Escalate when needed using flag_for_human

Rules:
1. ALWAYS call get_user_memory first so you know the user's history
2. ALWAYS call search_catalog before answering product questions
3. Never invent pricing or features not in the catalog
4. Be concise, warm, and focused on helping the prospect find the right plan
5. If you truly cannot answer, use flag_for_human rather than guessing

Format responses in plain text (no markdown). Be helpful and conversational."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": (
                "Search the NexusHQ product catalog for plans, pricing, features, "
                "add-ons, FAQs, integrations, and security. Always call before answering product questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query e.g. 'enterprise SSO pricing'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_memory",
            "description": (
                "Retrieve the user's prior conversation history. "
                "Always call this first to check for context from previous sessions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's unique identifier",
                    }
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_for_human",
            "description": "Escalate to a human sales rep when you cannot confidently answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "reason": {
                        "type": "string",
                        "description": "Why this needs human review",
                    },
                },
                "required": ["user_id", "reason"],
            },
        },
    },
]


def _dispatch_tool(name: str, args: dict, user_id: str, session_id: str, memory: MemoryBackend) -> dict:
    if name == "search_catalog":
        return {"result": search_catalog(args.get("query", ""))}
    elif name == "get_user_memory":
        return {"result": get_user_memory(args.get("user_id", user_id), memory)}
    elif name == "flag_for_human":
        return {"result": flag_for_human(args.get("user_id", user_id), args.get("reason", "Unknown"), session_id)}
    return {"result": f"Unknown tool: {name}"}


def run_agent(
    user_id: str,
    session_id: str,
    user_message: str,
    memory: MemoryBackend,
) -> tuple[str, list[str], str, str]:
    """
    Run the agentic loop for one user turn.
    Returns: assistant_response, tools_called, catalog_context, memory_context
    """
    tools_called: list[str] = []
    catalog_context = ""
    memory_context = ""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # Agentic loop
    while True:
        response = _CLIENT.chat.completions.create(
            model=_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        messages.append(msg)

        # No tool calls → return final text
        if not msg.tool_calls:
            return (
                (msg.content or "").strip(),
                list(dict.fromkeys(tools_called)),
                catalog_context,
                memory_context,
            )

        # Execute every tool call
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            logger.info("Tool call: %s args: %s", name, args)

            result = _dispatch_tool(name, args, user_id, session_id, memory)

            if name == "search_catalog":
                catalog_context = result["result"]
            elif name == "get_user_memory":
                memory_context = result["result"]

            tools_called.append(name)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })