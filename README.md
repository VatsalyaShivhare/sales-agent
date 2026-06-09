# NexusHQ Sales Assistant API

A production-ready, persistent AI sales assistant with cross-session memory, real tool use, and self-evaluation on every response.

**Live URL:** `https://sales-agent-production.up.railway.app`

---

## Architecture Diagram

```
                        ┌──────────────────────────────────────────┐
                        │              FastAPI  (main.py)           │
                        │         POST /chat/{user_id}              │
                        └──────────────────┬───────────────────────┘
                                           │
                                           ▼
                        ┌──────────────────────────────────────────┐
                        │          Chat Service                     │
                        │  1. Resolve / create session_id           │
                        │  2. Persist user message → DB             │
                        │  3. Call Agent Loop                       │
                        │  4. Call Eval Service                     │
                        │  5. Persist assistant message + eval → DB │
                        │  6. Return ChatResponse                   │
                        └──────────────────┬───────────────────────┘
                                           │
                              ┌────────────▼────────────┐
                              │      Agent Loop          │
                              │  (Anthropic tool-use API)│
                              └────────────┬────────────┘
                                           │
                   ┌───────────────────────┼──────────────────────┐
                   │                       │                       │
                   ▼                       ▼                       ▼
         ┌─────────────────┐   ┌───────────────────┐   ┌──────────────────┐
         │ search_catalog  │   │  get_user_memory   │   │  flag_for_human  │
         │                 │   │                    │   │                  │
         │ Keyword search  │   │ Queries SQLite DB  │   │ Writes to flag   │
         │ over catalog    │   │ for user history   │   │ log, notifies    │
         │ .json           │   │ via Memory Backend │   │ reviewer         │
         └────────┬────────┘   └────────┬───────────┘   └────────┬─────────┘
                  │                     │                          │
                  └─────────────────────┼──────────────────────────┘
                                        │
                                        ▼
                        ┌───────────────────────────────┐
                        │       Memory Backend          │
                        │  (abstraction layer)          │
                        │                               │
                        │  SQLiteMemoryBackend          │
                        │  ↳ SQLAlchemy → SQLite        │
                        │  (swap: change factory.py)    │
                        └───────────────────────────────┘
                                        │
                                        ▼
                        ┌───────────────────────────────┐
                        │      Eval Service             │
                        │  Prompted self-score via      │
                        │  second LLM call:             │
                        │  groundedness / relevance /   │
                        │  confidence / flagged         │
                        └───────────────────────────────┘
```

**Message flow (numbered):**

1. `POST /chat/{user_id}` arrives at the route handler
2. Chat service saves the user message and calls the agent
3. Agent calls `get_user_memory` → DB returns prior session context
4. Agent calls `search_catalog` → searches catalog.json for relevant product info
5. Agent synthesizes a response (and optionally calls `flag_for_human`)
6. Eval service calls the LLM a second time with a QA prompt to produce scores
7. Assistant message + eval scores are persisted to the DB
8. Structured `ChatResponse` (response + eval + tools_called + session_id) returned

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat/{user_id}` | Send message, get response + eval |
| GET | `/chat/{user_id}/history` | Full conversation history across all sessions |
| DELETE | `/chat/{user_id}/memory` | GDPR-style memory wipe |
| GET | `/chat/{user_id}/evals` | Aggregated eval stats |
| GET | `/catalog` | Product/pricing catalog |
| GET | `/health` | Service health check |
| GET | `/admin/flags` | Conversations flagged for human review |

Interactive docs: `https://sales-agent-production.up.railway.app/docs`

---

## Cross-Session Memory Demo

These two curl commands demonstrate memory working across separate sessions. The second call has **no knowledge** of the first call's content in its request body — it's retrieved entirely from the DB.

**Call 1 — establish context:**
```bash
curl -s -X POST "https://sales-agent-production.up.railway.app/chat/prospect_42" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hi! I run a 30-person startup. We need SSO and audit logs. What plan fits us?"}' \
  | jq '{response, session_id, tools_called, "confidence": .eval.confidence}'
```

**Call 2 — new session, references prior context:**
```bash
curl -s -X POST "https://sales-agent-production.up.railway.app/chat/prospect_42" \
  -H "Content-Type: application/json" \
  -d '{"message": "What was the price you mentioned for that plan? And does it include a free trial?"}' \
  | jq '{response, session_id, tools_called, "confidence": .eval.confidence}'
```

In Call 2, `session_id` is omitted — a new session is created. The agent calls `get_user_memory` automatically and retrieves that the user discussed Enterprise pricing in the prior session. The response correctly references $499/mo and the 14-day trial without the caller re-sending that context.

---

## Memory Design

**What I built:**

Memory is stored as flat message rows in SQLite (via SQLAlchemy). Each row has `user_id`, `session_id`, `role`, `content`, and eval columns. Sessions are logical — they're just a UUID grouping within the same user's row set.

The `MemoryBackend` abstract base class (`memory/base.py`) defines the interface. The concrete `SQLiteMemoryBackend` implements it. Swapping backends means:
1. Implement `MemoryBackend` in a new file
2. Change the import in `memory/factory.py` — one line

**Why this approach:**

- SQLite is zero-dependency for local dev and Railway's ephemeral disk
- SQLAlchemy means a single env var swap (`DATABASE_URL`) migrates to Postgres
- The abstraction layer means Mem0, Redis, or a vector DB can be dropped in for a production memory tier

**What I'd use at scale:**

- **Postgres** (via Railway or Supabase) for multi-instance deployments
- **Mem0 or Zep** for semantic memory search — the current implementation uses keyword matching over recent messages; a vector DB would enable retrieval by semantic similarity across thousands of sessions
- **Memory summarization**: a background job (Celery/ARQ) that condenses messages older than N turns into a compact summary, reducing token usage in the context window

---

## Eval Design

**How it works:**

Every assistant response triggers a second LLM call (`eval_service.py`) with a strict QA system prompt. The evaluator receives:
- The user's question
- The catalog context that was available
- The memory context that was available
- The assistant's response

It scores three dimensions (0–1 floats) and returns structured JSON:

```json
{
  "groundedness": 0.91,
  "relevance": 0.88,
  "confidence": 0.85,
  "flagged": false,
  "reasoning": "Response sourced directly from catalog..."
}
```

`flagged: true` is triggered when confidence < 0.65 or the response contains hallucinated claims. Flagged responses are logged and queryable via `/admin/flags`.

**Limitations:**

- LLM self-evaluation has known bias (models tend to rate themselves generously)
- The eval call adds ~500ms latency to every response
- The eval model is the same model as the agent — a separate smaller model would be cheaper and less self-serving

**What I'd replace it with in production:**

- **Ragas** for RAG-specific evaluation (faithfulness, answer relevancy, context precision)
- A separate fine-tuned eval model (e.g., GPT-4o-mini with golden examples)
- **Human-in-the-loop feedback loop**: store thumbs-up/down ratings from the sales team and use them to calibrate the automated scores over time

---

## Project Structure

```
sales-agent/
├── main.py                      # FastAPI app + lifespan
├── catalog.json                 # Product/pricing data
├── requirements.txt
├── Procfile                     # Railway/Heroku start command
├── railway.json                 # Railway deployment config
└── app/
    ├── api/
    │   └── routes.py            # Route handlers (thin layer only)
    ├── agents/
    │   └── agent.py             # Agentic loop, tool definitions
    ├── memory/
    │   ├── base.py              # Abstract MemoryBackend interface
    │   ├── sqlite_backend.py    # SQLite implementation
    │   └── factory.py          # ← swap backends here (one file)
    ├── tools/
    │   ├── catalog_tool.py      # search_catalog()
    │   ├── memory_tool.py       # get_user_memory()
    │   └── flag_tool.py         # flag_for_human()
    ├── services/
    │   ├── chat_service.py      # Orchestrates agent + memory + eval
    │   └── eval_service.py      # Self-scoring logic
    ├── models/
    │   └── schemas.py           # Pydantic request/response models
    └── db/
        ├── database.py          # SQLAlchemy engine + session
        └── models.py            # ORM Message model
```

---

## Local Development

```bash
git clone <repo>
cd sales-agent
cp .env.example .env          # add your ANTHROPIC_API_KEY
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000/docs
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | required | Anthropic API key |
| `DATABASE_URL` | `sqlite:///./sales_agent.db` | SQLAlchemy DB URL |
| `PORT` | `8000` | Injected by Railway |

To switch to Postgres: `DATABASE_URL=postgresql://user:pass@host/db` — no other changes needed.
