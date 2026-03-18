"""Prompt optimizer — rewrites a prompt using Haiku with conversation context."""

import json
import anthropic
from mcp_server.config import settings
from storage.db import get_stack_memory

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = """\
You are an expert prompt engineer embedded in a developer's IDE. Your job is to take a user's
raw prompt and rewrite it so it is clearer, more specific, and more likely to produce a
high-quality response from a coding assistant — WITHOUT changing the user's intent.

You will receive:
  • The original prompt
  • Recent conversation history so you understand the user's stack, domain, and intent

Return a JSON object with exactly these keys:
  "optimized_prompt" : the rewritten prompt (string)
  "reason"           : one sentence explaining the main improvement (string)
  "changes_made"     : list of short strings, each describing one specific change

Respond ONLY with valid JSON. No markdown fences, no extra commentary.\
"""


def optimize(prompt: str, history: list) -> dict:
    """Rewrite *prompt* using conversation *history* and learned stack context.

    Always returns a dict with keys: optimized_prompt, reason, changes_made.
    Falls back to the original prompt on any error.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # ── Inject learned stack memory into the system prompt ────────────────────
    try:
        stack_memory = get_stack_memory()
    except Exception:
        stack_memory = {}

    memory_context = ""
    if stack_memory:
        lines = [f"  - {k}: {v}" for k, v in stack_memory.items()]
        memory_context = (
            "\n\nUser's known stack (learned from past sessions):\n"
            + "\n".join(lines)
            + "\n\nUse this context when rewriting the prompt — inject the "
              "correct language/framework/style even if not stated explicitly.\n"
        )

    # ── Build conversation history block ─────────────────────────────────────
    history_text = ""
    if history:
        recent = history[-6:]
        history_text = "\n".join(
            f"{turn.get('role', 'user').upper()}: {turn.get('content', '')}"
            for turn in recent
        )
        history_text = f"\n\nConversation history:\n{history_text}\n"

    user_message = f"Original prompt:{history_text}\n{prompt}"

    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=512,
            system=_SYSTEM + memory_context,
            messages=[{"role": "user", "content": user_message}],
        )
        data = json.loads(response.content[0].text.strip())
        return {
            "optimized_prompt": data.get("optimized_prompt", prompt),
            "reason": data.get("reason", ""),
            "changes_made": data.get("changes_made", []),
        }
    except Exception:
        return {
            "optimized_prompt": prompt,
            "reason": "Optimization unavailable; original prompt returned.",
            "changes_made": [],
        }
