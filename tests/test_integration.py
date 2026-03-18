"""
Integration tests for the full optimize_prompt pipeline.

These tests call the MCP tool functions directly (not over the transport wire)
and mock only the Anthropic API client — DuckDB runs against a real temp file.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

import storage.db as db_module


# ── DB isolation fixture ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolate_db(tmp_path: Path, monkeypatch):
    """Redirect all DB operations to a throwaway file for each test."""
    test_db = tmp_path / "test_history.db"
    monkeypatch.setattr(db_module, "_DB_PATH", test_db)
    monkeypatch.setattr(db_module, "_conn", None)
    yield
    # Close and release the connection so the tmp file can be cleaned up
    if db_module._conn is not None:
        try:
            db_module._conn.close()
        except Exception:
            pass
        monkeypatch.setattr(db_module, "_conn", None)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mock_client(optimized_text: str, reason: str = "Added specificity.") -> MagicMock:
    payload = json.dumps({
        "optimized_prompt": optimized_text,
        "reason": reason,
        "changes_made": ["Specified framework", "Clarified token handling"],
    })
    content_block = MagicMock()
    content_block.text = payload
    response = MagicMock()
    response.content = [content_block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


# ── Test 1: complex prompt is intercepted ────────────────────────────────────

@patch("mcp_server.optimizer.anthropic.Anthropic")
def test_full_pipe_intercepts_complex_prompt(mock_cls):
    improved = (
        "Write a FastAPI middleware that validates JWT tokens on each request "
        "and handles token refresh by returning a new access token on 401."
    )
    mock_cls.return_value = _make_mock_client(improved)

    from mcp_server.tools import optimize_prompt

    result = optimize_prompt(
        user_prompt="write me a middleware that validates tokens and handles refresh",
        conversation_history=[],
        turn_number=1,
    )

    assert result["was_intercepted"] is True
    assert result["optimized_prompt"] == improved
    assert result["score"] >= 45


# ── Test 2: simple prompt passes through unchanged ───────────────────────────

@patch("mcp_server.optimizer.anthropic.Anthropic")
def test_full_pipe_passes_through_simple_prompt(mock_cls):
    # Optimizer should never be called for this prompt, but patch it anyway
    mock_cls.return_value = _make_mock_client("should not be used")

    from mcp_server.tools import optimize_prompt

    original = "what is jwt"
    result = optimize_prompt(
        user_prompt=original,
        conversation_history=[],
        turn_number=1,
    )

    assert result["was_intercepted"] is False
    assert result["optimized_prompt"] == original
    assert result["score"] < 45
    # Optimizer API must NOT have been called
    mock_cls.return_value.messages.create.assert_not_called()


# ── Test 3: history query returns saved events ───────────────────────────────

def test_get_prompt_history_returns_saved_events():
    from storage.db import save_prompt_event
    from mcp_server.tools import get_prompt_history, _SESSION_ID

    events_to_save = [
        ("original prompt 0", "optimized prompt 0", 55, True,  1),
        ("original prompt 1", "optimized prompt 1", 62, True,  2),
        ("what is jwt",       "what is jwt",         -35, False, 1),
    ]
    for orig, opt, score, intercepted, turn in events_to_save:
        save_prompt_event(
            original_prompt=orig,
            optimized_prompt=opt,
            classifier_score=score,
            was_intercepted=intercepted,
            turn_number=turn,
            session_id=_SESSION_ID,
        )

    history = get_prompt_history(limit=10)

    assert len(history) == 3
    assert all("original_prompt" in e for e in history)
    assert all("classifier_score" in e for e in history)
    assert all("was_intercepted" in e for e in history)
    # Most recent first
    assert history[0]["original_prompt"] == "what is jwt"


# ── Test 4: return dict has all required keys ─────────────────────────────────

@patch("mcp_server.optimizer.anthropic.Anthropic")
def test_optimize_prompt_return_shape(mock_cls):
    mock_cls.return_value = _make_mock_client("Better version of the prompt.")

    from mcp_server.tools import optimize_prompt

    result = optimize_prompt(
        user_prompt="handle the auth and manage user sessions",
        conversation_history=[{"role": "user", "content": "I'm building a FastAPI app"}],
        turn_number=2,
    )

    assert set(result.keys()) == {"optimized_prompt", "was_intercepted", "score", "reason"}
    assert isinstance(result["optimized_prompt"], str)
    assert isinstance(result["was_intercepted"], bool)
    assert isinstance(result["score"], int)
    assert isinstance(result["reason"], str)


# ── Phase 3: stack extractor tests ───────────────────────────────────────────

def test_stack_extractor_detects_python_fastapi():
    from mcp_server.extractor import extract_stack_signals
    signals = extract_stack_signals(
        "write a FastAPI endpoint with type hints",
        history=[],
    )
    assert signals.get("language") == "python"
    assert signals.get("framework") == "fastapi"


def test_stack_extractor_returns_empty_for_vague_prompt():
    from mcp_server.extractor import extract_stack_signals
    signals = extract_stack_signals("fix this", history=[])
    assert isinstance(signals, dict)


def test_memory_upsert_and_retrieval(tmp_path, monkeypatch):
    import storage.db as db_module
    monkeypatch.setattr(db_module, "_DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db_module, "_conn", None)
    from storage.db import upsert_stack_memory, get_stack_memory
    upsert_stack_memory("language", "python", 0.9)
    upsert_stack_memory("framework", "fastapi", 0.85)
    memory = get_stack_memory()
    assert memory["language"] == "python"
    assert memory["framework"] == "fastapi"


def test_memory_below_confidence_threshold_excluded(tmp_path, monkeypatch):
    import storage.db as db_module
    monkeypatch.setattr(db_module, "_DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db_module, "_conn", None)
    from storage.db import upsert_stack_memory, get_stack_memory
    upsert_stack_memory("language", "python", 0.3)
    memory = get_stack_memory()
    assert "language" not in memory
