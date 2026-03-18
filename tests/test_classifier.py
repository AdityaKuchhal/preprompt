"""Tests for the pure-heuristic prompt classifier."""

import pytest
from mcp_server.classifier import classify_prompt, OPTIMIZATION_THRESHOLD


# ── Required test cases from spec ────────────────────────────────────────────

def test_complex_middleware_prompt_triggers_optimization():
    """Multi-verb, multi-requirement dev prompt must score >= 45."""
    score = classify_prompt(
        "write me a middleware that validates tokens and handles refresh",
        history=[],
        turn=1,
    )
    assert score >= OPTIMIZATION_THRESHOLD, f"Expected >= {OPTIMIZATION_THRESHOLD}, got {score}"


def test_what_is_jwt_does_not_trigger():
    """Simple lookup question must score < 45."""
    score = classify_prompt("what is jwt", history=[], turn=1)
    assert score < OPTIMIZATION_THRESHOLD, f"Expected < {OPTIMIZATION_THRESHOLD}, got {score}"


def test_thanks_does_not_trigger():
    """Conversational acknowledgement must score < 45."""
    score = classify_prompt("thanks", history=[], turn=1)
    assert score < OPTIMIZATION_THRESHOLD, f"Expected < {OPTIMIZATION_THRESHOLD}, got {score}"


# ── Negative signal tests ─────────────────────────────────────────────────────

def test_short_prompt_penalised():
    score_short = classify_prompt("fix it", history=[], turn=1)
    score_long = classify_prompt("fix the authentication middleware so it handles token expiry", history=[], turn=1)
    assert score_short < score_long


def test_what_does_question_penalised():
    score = classify_prompt("what does this function do", history=[], turn=1)
    assert score < OPTIMIZATION_THRESHOLD


def test_what_are_penalised():
    score = classify_prompt("what are the best practices for REST APIs", history=[], turn=1)
    assert score < OPTIMIZATION_THRESHOLD


def test_numbered_steps_penalised():
    score = classify_prompt(
        "1. Create a FastAPI endpoint\n2. Add JWT auth\n3. Return a token",
        history=[],
        turn=1,
    )
    assert score < OPTIMIZATION_THRESHOLD


def test_conversational_openers_penalised():
    for opener in ["yes please", "ok do that", "cool thanks", "sure go ahead"]:
        score = classify_prompt(opener, history=[], turn=1)
        assert score < OPTIMIZATION_THRESHOLD, f"'{opener}' should score < 45, got {score}"


# ── Positive signal tests ─────────────────────────────────────────────────────

def test_multi_requirement_raises_score():
    base = classify_prompt("write a function", history=[], turn=1)
    multi = classify_prompt(
        "write a function that handles auth, manages sessions, and deals with refresh tokens",
        history=[],
        turn=1,
    )
    assert multi > base


def test_turn_depth_raises_score():
    early = classify_prompt("update the auth logic", history=[], turn=1)
    late = classify_prompt("update the auth logic", history=[], turn=5)
    assert late > early


def test_code_task_without_format_raises_score():
    with_format = classify_prompt(
        "write a function that returns a json object for user auth", history=[], turn=1
    )
    without_format = classify_prompt(
        "write a function for user auth", history=[], turn=1
    )
    assert without_format >= with_format


def test_score_is_integer():
    score = classify_prompt("build an API endpoint", history=[], turn=1)
    assert isinstance(score, int)
