"""DuckDB storage for PromptForge — persists to ~/.promptforge/history.db."""

import uuid
import duckdb
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DB_PATH = Path.home() / ".promptforge" / "history.db"
_conn: Optional[duckdb.DuckDBPyConnection] = None


def _get_connection() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = duckdb.connect(str(_DB_PATH))
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS prompt_history (
                id               VARCHAR PRIMARY KEY,
                timestamp        TIMESTAMP,
                original_prompt  TEXT,
                optimized_prompt TEXT,
                classifier_score INTEGER,
                was_intercepted  BOOLEAN,
                turn_number      INTEGER,
                session_id       VARCHAR
            )
        """)
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS stack_memory (
                id           VARCHAR PRIMARY KEY,
                updated_at   TIMESTAMP,
                key          VARCHAR UNIQUE,
                value        TEXT,
                confidence   FLOAT,
                source_count INTEGER
            )
        """)
    return _conn


# ── Existing functions (unchanged) ────────────────────────────────────────────

def save_prompt_event(
    original_prompt: str,
    optimized_prompt: str,
    classifier_score: int,
    was_intercepted: bool,
    turn_number: int,
    session_id: str,
) -> str:
    """Insert a prompt event and return its generated id."""
    event_id = str(uuid.uuid4())
    conn = _get_connection()
    conn.execute("""
        INSERT INTO prompt_history
            (id, timestamp, original_prompt, optimized_prompt,
             classifier_score, was_intercepted, turn_number, session_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        event_id,
        datetime.now(timezone.utc),
        original_prompt,
        optimized_prompt,
        classifier_score,
        was_intercepted,
        turn_number,
        session_id,
    ])
    return event_id


def get_recent_history(session_id: str, limit: int = 20) -> list[dict]:
    """Return the most recent *limit* events for *session_id*."""
    conn = _get_connection()
    rows = conn.execute("""
        SELECT id, timestamp, original_prompt, optimized_prompt,
               classifier_score, was_intercepted, turn_number, session_id
        FROM prompt_history
        WHERE session_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, [session_id, limit]).fetchall()
    cols = ["id", "timestamp", "original_prompt", "optimized_prompt",
            "classifier_score", "was_intercepted", "turn_number", "session_id"]
    return [dict(zip(cols, row)) for row in rows]


# ── Stack memory functions ─────────────────────────────────────────────────────

def upsert_stack_memory(key: str, value: str, confidence: float) -> None:
    """Insert or update a stack memory entry, incrementing source_count."""
    conn = _get_connection()
    existing = conn.execute(
        "SELECT id, source_count FROM stack_memory WHERE key = ?", [key]
    ).fetchone()

    if existing:
        entry_id, source_count = existing
        conn.execute("""
            UPDATE stack_memory
            SET updated_at = ?, value = ?, confidence = ?, source_count = ?
            WHERE id = ?
        """, [datetime.now(timezone.utc), value, confidence, source_count + 1, entry_id])
    else:
        conn.execute("""
            INSERT INTO stack_memory (id, updated_at, key, value, confidence, source_count)
            VALUES (?, ?, ?, ?, ?, 1)
        """, [str(uuid.uuid4()), datetime.now(timezone.utc), key, value, confidence])


def get_stack_memory() -> dict[str, str]:
    """Return all memory entries as {key: value} where confidence >= 0.6."""
    conn = _get_connection()
    rows = conn.execute("""
        SELECT key, value FROM stack_memory
        WHERE confidence >= 0.6
        ORDER BY confidence DESC
    """).fetchall()
    return {row[0]: row[1] for row in rows}


def get_full_stack_memory() -> list[dict]:
    """Return all entries including confidence and source_count for CLI display."""
    conn = _get_connection()
    rows = conn.execute("""
        SELECT key, value, confidence, source_count, updated_at
        FROM stack_memory
        ORDER BY confidence DESC
    """).fetchall()
    cols = ["key", "value", "confidence", "source_count", "updated_at"]
    return [dict(zip(cols, row)) for row in rows]
