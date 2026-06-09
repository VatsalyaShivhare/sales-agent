"""
search_catalog — keyword + semantic search over the product catalog.

Loaded once at startup from catalog.json. Returns structured text
the agent can cite directly in its response.
"""
import json
import os
import re
from pathlib import Path


# ── Load catalog once at import time ─────────────────────────────────────────

_CATALOG_PATH = Path(__file__).parent.parent.parent / "catalog.json"

with open(_CATALOG_PATH, "r") as f:
    _CATALOG: dict = json.load(f)


def get_full_catalog() -> dict:
    return _CATALOG


def _catalog_text_chunks() -> list[tuple[str, str]]:
    """
    Flatten the catalog into (label, text) pairs for keyword matching.
    Called lazily; cached in module scope after first call.
    """
    chunks = []

    # Plans
    for plan in _CATALOG.get("plans", []):
        text = (
            f"Plan: {plan['name']} | Price: {plan['price']} | "
            f"Annual: {plan.get('annual_price', 'N/A')} | "
            f"Users: {plan['users']} | "
            f"Features: {', '.join(plan['features'])} | "
            f"Best for: {plan.get('best_for', '')} | "
            f"Not included: {', '.join(plan.get('not_included', []) or ['nothing'])}"
        )
        chunks.append((f"plan:{plan['name']}", text))

    # Add-ons
    for addon in _CATALOG.get("add_ons", []):
        text = (
            f"Add-on: {addon['name']} | Price: {addon['price']} | "
            f"Available on: {', '.join(addon['available_on'])}"
        )
        chunks.append((f"addon:{addon['name']}", text))

    # FAQs
    for faq in _CATALOG.get("faqs", []):
        text = f"FAQ: {faq['q']} → {faq['a']}"
        chunks.append(("faq", text))

    # Integrations
    integrations = _CATALOG.get("integrations", [])
    chunks.append(("integrations", f"Integrations: {', '.join(integrations)}"))

    # Security
    sec = _CATALOG.get("security", {})
    chunks.append((
        "security",
        f"Security: Encryption: {sec.get('encryption')} | "
        f"Compliance: {', '.join(sec.get('compliance', []))} | "
        f"Auth: {', '.join(sec.get('auth', []))} | "
        f"Data residency: {', '.join(sec.get('data_residency', []))}",
    ))

    return chunks


_CHUNKS = _catalog_text_chunks()


def search_catalog(query: str) -> str:
    """
    Search the product catalog for information matching `query`.
    Returns a formatted string of the most relevant catalog sections.
    
    This is a registered LLM tool — called by the agent loop.
    """
    if not query or not query.strip():
        return "Please provide a search query."

    query_lower = query.lower()
    keywords = re.split(r"[\s,?./]+", query_lower)
    keywords = [k for k in keywords if len(k) > 2]

    # Score each chunk by keyword overlap
    scored: list[tuple[int, str, str]] = []
    for label, text in _CHUNKS:
        text_lower = text.lower()
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scored.append((score, label, text))

    # Sort descending; return top 5
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:5]

    if not top:
        return (
            "No direct catalog matches found. "
            "Available plans: Starter ($49/mo), Growth ($199/mo), Enterprise ($499/mo)."
        )

    result_lines = [f"[Catalog search results for: '{query}']"]
    for _, label, text in top:
        result_lines.append(f"• {text}")

    return "\n".join(result_lines)
