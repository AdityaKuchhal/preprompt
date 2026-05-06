<!-- Last updated: 2026-04-29 23:18 -->
# PrePrompt — CONTEXT.md
# This file is auto-maintained. Read it fully at the start of every chat.

## Build status
Phase 9b complete. 29/29 tests passing.

## What PrePrompt does
MCP server that intercepts prompts in Claude Code and Cursor, scores them
with a heuristic classifier (no API), optimizes complex ones using Claude
Haiku, logs everything to SQLite (WAL mode), and learns the user's stack
over time via a memory layer. Runs entirely locally.

## Tech stack
- Python 3.11+, FastMCP, Anthropic SDK, SQLite (WAL mode), pydantic-settings
- Haiku model: claude-haiku-4-5-20251001
- DB: SQLite WAL at ~/.preprompt/history.db

## File map
mcp_server/
  server.py      — entry point, mcp.run(transport=settings.mcp_transport)
  tools.py       — MCP tools: optimize_prompt, get_prompt_history
                   uses get_or_create_session() for stable daily session identity
  classifier.py  — pure heuristic scorer, threshold=38, multi-req weight=12/hit, no API calls
  optimizer.py   — Haiku API call + memory context injection
                   strips markdown fences from model JSON response
  extractor.py   — heuristic stack signal extractor
  config.py      — pydantic-settings, reads .env

storage/
  db.py          — SQLite WAL: prompt_history + stack_memory + sessions tables
                   prompt_history has user_kept column (NULL=unrated, 1=kept, 0=rejected)
                   record_user_feedback(event_id, kept) — saves accept/reject
                   get_feedback_stats() — returns accept_rate, kept, rejected counts
                   Sidecar pattern: hook writes JSON to ~/.preprompt/pending/,
                   flushed by MCP server or CLI commands via flush_pending_hook_events()
                   flush_pending_hook_events() also calls update_memory_from_prompt()
                   so Claude Code sessions contribute to stack memory
                   get_or_create_session(): stable {hostname}-{date} session key
                   race-safe: INSERT OR IGNORE + _session_lock (threading.Lock)
                   handles Cursor spawning multiple MCP server processes simultaneously
                   get_all_history(): cross-session history query
                   upsert_stack_memory(): compounding confidence (+0.03/hit, reset on value change)

cli/
  commands.py    — preprompt-history, stats, memory, test-classifier,
                   clip (cross-platform clipboard optimizer), optimize,
                   feedback (accept/reject rating), install (one-command setup),
                   update, update-context
                   stats_cmd/history_cmd call maybe_run_setup() on first run
  setup.py       — first-run API key wizard (maybe_run_setup())
  watch.py       — preprompt-watch: auto-flushes sidecars on startup, live tail of ~/.preprompt/activity.log

.claude/
  settings.json           — MCP server + UserPromptSubmit hook config
  hooks/pre_prompt.py     — interception hook with rich box annotation on stderr
                            path resolved via __file__ (CWD-independent)
                            writes JSON sidecar to ~/.preprompt/pending/ — never touches DB directly
                            appends every event to ~/.preprompt/activity.log via _log_activity()

scripts/
  install.sh              — one-command installer (auto-detects Claude Code, Cursor, Windsurf, Zed)
  setup_global_hook.py    — global Claude Code MCP + UserPromptSubmit registration
  install_cursor.py       — registers MCP in ~/.cursor/mcp.json
  install_windsurf.py     — registers MCP in ~/.codeium/windsurf/mcp_config.json
  install_zed.py          — registers MCP in ~/.config/zed/settings.json
  init_github.py          — git init + first commit + push instructions

.github/
  workflows/ci.yml        — runs pytest on every push/PR
  workflows/publish.yml   — builds + publishes to PyPI on git tag v*

preprompt.skill.md        — Claude Skill file for tools without MCP hook support

LICENSE                   — MIT

tests/
  test_classifier.py    — 12 tests
  test_optimizer.py     —  4 tests
  test_integration.py   — 13 tests (incl. activity log write test)

## Key interfaces — never change these signatures
- classify_prompt(prompt: str, history: list, turn: int) -> int
- optimize(prompt: str, history: list) -> dict
- optimize_prompt(user_prompt, conversation_history, turn_number) -> dict
- save_prompt_event(...) in storage/db.py
- get_recent_history(session_id, limit) in storage/db.py
- upsert_stack_memory(key, value, confidence) in storage/db.py
- get_stack_memory() -> dict[str, str] in storage/db.py
- extract_stack_signals(prompt, history) -> dict
- update_memory_from_prompt(prompt, history) -> None
- flush_pending_hook_events() -> int in storage/db.py

## Completed phases
- Phase 1: scaffold, classifier, optimizer, SQLite, MCP server
- Phase 2: hook, Cursor install, CLI commands
- Phase 3: stack memory, extractor, memory-aware optimizer
- Phase 4: GitHub, live test, CONTEXT.md
- Phase 5: session identity, memory consolidation, rich annotations, cross-session history
- Phase 6: packaging, SQLite WAL migration, sidecar concurrency pattern, classifier tuned (38/12), absolute hook path, one-command install, MIT license, distribution README
- Phase 6b: global rename PromptForge → PrePrompt
- Phase 7: GitHub Actions CI + publish workflow, PyPI trusted publisher setup
- Phase 7b: preprompt-optimize CLI command, Windsurf + Zed MCP installers
- Phase 7c: preprompt.skill.md — Claude Skill for tools without MCP support
- Phase 8: activity.log in hook, preprompt-watch live feed, preprompt-clip clipboard optimizer, session summary on server shutdown
- Phase 8b: flush sidecars runs memory extraction (Claude Code → stack memory), watch auto-flushes on startup
- Phase 8c: preprompt-update command, version check on stats/history, version in stats header
- Phase 9: accept/reject tracking, preprompt-feedback CLI, preprompt-install one-command setup, cross-platform clipboard, faster memory (0.85/+0.03), first-run API key wizard, Beehiiv beta signup wired
- Phase 9b: landing page upgrades — social proof strip, FAQ accordion, preprompt-install leads install section, v0.1.3 throughout, mobile ASCII box fixed (CSS card on mobile, full ASCII on desktop), beta signup matches paper/amber design
- Phase 9c: fix get_or_create_session() UNIQUE constraint race — INSERT OR IGNORE + threading.Lock, safe against concurrent Cursor MCP server processes

## Runtime files
- ~/.preprompt/history.db     — SQLite WAL database
- ~/.preprompt/pending/*.json — hook sidecars (flushed by MCP server)
- ~/.preprompt/activity.log   — plain-text event log (tailed by preprompt-watch)

## PyPI publish instructions
1. Create account at https://pypi.org
2. Go to https://pypi.org/manage/account/publishing/
3. Add trusted publisher: owner=yashdeeptehlan, repo=preprompt, workflow=publish.yml, env=release
4. Create GitHub environment "release" at https://github.com/yashdeeptehlan/preprompt/settings/environments
5. Tag a release: git tag v0.1.X && git push origin v0.1.X

## Next phases
- Phase 10: web dashboard — local FastAPI server showing live interception feed, before/after diffs, memory confidence scores, cost savings tracker
- Phase 10b: project profiles — separate memory per repo/project
- Phase 10c: clarify mode — ask questions instead of rewriting when intent is ambiguous
- Phase 11: VS Code extension for broader distribution

## GitHub Pages
Landing page: https://preprompt.org
Source: docs/index.html (React JSX via Babel standalone, JetBrains Mono + Inter Tight, paper/amber design system, sections: Nav, Hero, SocialProof, BeforeAfter, HowItWorks, ClassifierTable, StackMemory, Architecture, Cost, Install, FAQ, Beta, Footer)

## How new chats should start
User will say "continuing from last chat" or paste this file.
Ask for: cat preprompt/CONTEXT.md
Confirm phase + what comes next, then proceed.

## Environment
- Dev machine: macOS
- API key: in .env as ANTHROPIC_API_KEY
- Claude Code workspace: /Users/user/Documents/Promptforge/promptforge
- GitHub: https://github.com/yashdeeptehlan/preprompt

## Current version
v0.1.3 — live on PyPI at https://pypi.org/project/preprompt/

## Distribution
- PyPI: pip install preprompt
- GitHub: github.com/yashdeeptehlan/preprompt (public, MIT, 10 stars)
- Landing page: preprompt.org
- Email list: preprompt.beehiiv.com/subscribe

## Known limitations
- Cursor only works in Agent mode — Ask/Plan modes skip MCP tools entirely
- preprompt-watch stats show total=0 when MCP server holds write lock
- Stack memory builds slowly for brand new users (by design — confidence compounds)
- Claude Code hook fires globally across all projects on the machine

## Strategic context
The real opportunity is becoming an AI instruction reliability layer —
checking human intent before it reaches powerful AI agents. Current moat:
cross-tool portability, local-first privacy, user-owned memory, open source.
Not yet VC-ready — need 500+ active installs with retention data first.
Focus: grow individual users, collect accept/reject data proving retry reduction.
