"""MCP server entry point for PrePrompt."""

import sys
import atexit
import sqlite3
from pathlib import Path
from mcp_server.tools import mcp
from mcp_server.config import settings

_REGISTERED_TOOLS = ["optimize_prompt", "get_prompt_history"]


def _print_session_summary() -> None:
    """Print today's session stats on server shutdown."""
    try:
        db_path = Path.home() / ".preprompt" / "history.db"
        if not db_path.exists():
            return
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        row = conn.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN was_intercepted=1 THEN 1 ELSE 0 END),
                   ROUND(AVG(classifier_score), 1)
            FROM prompt_history
            WHERE date(timestamp) = date('now')
        """).fetchone()
        conn.close()
        total, intercepted, avg = row
        if not total:
            return
        intercepted = intercepted or 0
        pct = round(intercepted / total * 100) if total else 0
        print(
            f"\n  PrePrompt session summary\n"
            f"  prompts seen:    {total}\n"
            f"  intercepted:     {intercepted} ({pct}%)\n"
            f"  avg score:       {avg}\n",
            file=sys.stderr,
        )
    except Exception:
        pass


def main() -> None:
    # First-run setup: only prompt interactively, never when MCP stdio is in use
    try:
        if sys.stdin.isatty():
            from cli.setup import maybe_run_setup
            maybe_run_setup()
    except Exception:
        pass
    atexit.register(_print_session_summary)
    print("──────────────────────────────────────────", flush=True, file=sys.stderr)
    print("  PrePrompt MCP server starting…",            flush=True, file=sys.stderr)
    print(f"  Transport : {settings.mcp_transport}",    flush=True, file=sys.stderr)
    print(f"  Tools     : {', '.join(_REGISTERED_TOOLS)}", flush=True, file=sys.stderr)
    print("──────────────────────────────────────────", flush=True, file=sys.stderr)
    mcp.run(transport=settings.mcp_transport)


if __name__ == "__main__":
    main()
