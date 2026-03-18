#!/usr/bin/env python3
"""
Claude Code UserPromptSubmit hook for PromptForge.

Receives JSON on stdin, writes JSON to stdout.
  stdin:  {"prompt": "...", "conversation_history": [...], "turn_number": N}
  stdout: {"prompt": "..."}   ← optimized or original, never blocked
"""

import sys
import os
import json


def main() -> None:
    raw = sys.stdin.read()

    # Parse stdin — on failure, echo back whatever we got and exit cleanly
    try:
        data = json.loads(raw)
    except Exception:
        print(raw, end="")
        sys.exit(0)

    prompt: str = data.get("prompt", "")
    history: list = data.get("conversation_history", [])
    turn: int = data.get("turn_number", 1)

    def passthrough() -> None:
        print(json.dumps({"prompt": prompt}))

    try:
        # Always resolve paths relative to this file's location,
        # not the caller's working directory
        _HOOK_FILE = os.path.abspath(__file__)
        _HOOK_DIR = os.path.dirname(_HOOK_FILE)          # .claude/hooks/
        _CLAUDE_DIR = os.path.dirname(_HOOK_DIR)          # .claude/
        _PROJECT_ROOT = os.path.dirname(_CLAUDE_DIR)      # promptforge/

        # Add project root to path so mcp_server + storage imports work
        if _PROJECT_ROOT not in sys.path:
            sys.path.insert(0, _PROJECT_ROOT)

        # Load .env from project root
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

        # ── Classify (no API call — always fast) ──────────────────────────────
        from mcp_server.classifier import classify_prompt, OPTIMIZATION_THRESHOLD

        score = classify_prompt(prompt, history, turn)

        if score < OPTIMIZATION_THRESHOLD:
            passthrough()
            sys.exit(0)

        # ── Check API key before importing optimizer (which triggers config) ──
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            print(
                "[PromptForge WARNING] ANTHROPIC_API_KEY not set — skipping optimization",
                file=sys.stderr,
            )
            passthrough()
            sys.exit(0)

        # ── Optimize via Haiku API ────────────────────────────────────────────
        from mcp_server.optimizer import optimize
        from storage.db import save_prompt_event

        result = optimize(prompt, history)
        optimized: str = result["optimized_prompt"]
        reason: str = result["reason"]
        was_intercepted: bool = optimized != prompt

        save_prompt_event(
            original_prompt=prompt,
            optimized_prompt=optimized,
            classifier_score=score,
            was_intercepted=was_intercepted,
            turn_number=turn,
            session_id="hook-session",
        )

        # ── Update stack memory (failure must never block the hook) ───────────
        try:
            from mcp_server.extractor import update_memory_from_prompt
            update_memory_from_prompt(prompt, history)
        except Exception as mem_err:
            print(f"[PromptForge] Memory update failed: {mem_err}", file=sys.stderr)

        print(f"[PromptForge +{score}] {reason}", file=sys.stderr)
        print(json.dumps({"prompt": optimized}))

    except Exception as e:
        print(f"[PromptForge ERROR] {e}", file=sys.stderr)
        passthrough()

    sys.exit(0)


if __name__ == "__main__":
    main()
