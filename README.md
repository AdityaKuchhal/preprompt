# PromptForge

An MCP server that intercepts prompts inside Claude Code and Cursor, scores
them with a fast heuristic classifier, and rewrites under-specified ones with
an AI optimizer before they reach the LLM — transparently and in real time.

---

## How it works

```
User types prompt
      │
      ▼
 classifier (heuristic, no API call) ──► score < 45? ──► pass through unchanged
                                                │
                                           score ≥ 45
                                                │
                                                ▼
                                      optimizer (Haiku API)
                                                │
                                                ▼
                                        log to DuckDB
                                                │
                                                ▼
                                   return best prompt to LLM
```

The classifier runs entirely in-process with no network call, so non-intercepted
prompts add zero latency. The optimizer only fires when it's likely to help.

---

## How the classifier works

Scoring is purely heuristic — no LLM involved:

- **Positive signals** (add points): vague action verbs ("handle", "manage",
  "fix", "deal with"), multi-requirement density (count of "and" / commas),
  late conversation turns (turn 3+), code task with no output format specified.
- **Negative signals** (subtract points): prompt under 6 words (−20),
  starts with "what is/does/are" (−15), contains numbered steps or explicit
  format hint (−15), conversational opener like "thanks" or "ok" (−25).
- **Threshold**: score ≥ 45 triggers the Haiku optimizer call.

To tune the threshold: edit `OPTIMIZATION_THRESHOLD` in
`mcp_server/classifier.py` (default: 45).

---

## Setup

```bash
# 1. Install
cd promptforge
pip install -e ".[dev]"   # or: uv pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# open .env and set ANTHROPIC_API_KEY

# 3. Verify
pytest                          # 16+ tests, no API calls needed
promptforge-test-classifier     # quick sanity check on the scorer

# 4. Start the MCP server
python -m mcp_server.server
```

---

## Register with Claude Code

`.claude/settings.json` (already in this repo) registers both the MCP server
and the `UserPromptSubmit` hook automatically when you open the project in
Claude Code. No extra steps needed — just restart Claude Code.

If you want to register globally instead, add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "promptforge": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/promptforge",
      "env": { "PYTHONPATH": "/absolute/path/to/promptforge" }
    }
  }
}
```

---

## Register with Cursor

```bash
python scripts/install_cursor.py
# ✓ PromptForge registered in ~/.cursor/mcp.json
# ↻ Restart Cursor for changes to take effect
```

---

## MCP Tools

| Tool | Parameters | Returns |
|------|-----------|---------|
| `optimize_prompt` | `user_prompt`, `conversation_history`, `turn_number` | `{optimized_prompt, was_intercepted, score, reason}` |
| `get_prompt_history` | `limit` (default 20) | list of recent prompt events for this session |

---

## CLI Commands

```
promptforge-test-classifier     # benchmark the scorer against 6 prompts
promptforge-history             # recent prompt log (all sessions)
promptforge-history --limit 50 --intercepted-only
promptforge-stats               # aggregate stats
```

Example output — `promptforge-history`:

```
TIME      SCORE  INT  ORIGINAL PROMPT
──────────────────────────────────────────────────────────────────────────────
2m ago       72  yes  write me a middleware that validates tokens and handl...
5m ago       18  no   what is jwt
```

Example output — `promptforge-stats`:

```
 PromptForge — optimization stats
──────────────────────────────────────────────────
 Total prompts seen:      847
 Prompts intercepted:     312 (36.8%)
 Avg classifier score:    41.2
 Avg score (intercepted): 67.4
 Sessions tracked:        23
 DB path:                 /Users/you/.promptforge/history.db
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required for optimizer |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `sse` |

Storage is always at `~/.promptforge/history.db` (created automatically).

---

## Test the hook manually

```bash
echo '{"prompt":"write me a middleware that validates tokens and handles refresh","conversation_history":[],"turn_number":3}' \
  | python .claude/hooks/pre_prompt.py
```
