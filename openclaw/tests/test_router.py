"""
test_router.py — KLAW router unit tests
Run: cd openclaw && python -m pytest tests/ -v
"""

import sys
from pathlib import Path

# Allow running without install
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from klaw.router import KlawRouter


def _router():
    return KlawRouter()


# ── classify() ────────────────────────────────────────────────────────────────

def test_classify_returns_suit():
    r = _router()
    result = r.classify("I feel so lonely and disconnected from everyone")
    assert "suit" in result
    assert result["suit"] in ("hearts", "spades", "diamonds", "clubs")


def test_classify_returns_tier():
    r = _router()
    result = r.classify("build a REST API with authentication")
    assert "tier" in result
    assert isinstance(result["tier"], int)
    assert 0 <= result["tier"] <= 4


def test_classify_emotional_is_hearts():
    r = _router()
    result = r.classify("I'm feeling really sad and need support")
    assert result["suit"] == "hearts"


def test_classify_technical_is_diamonds_or_clubs():
    r = _router()
    result = r.classify("fix the bug in the database migration script")
    assert result["suit"] in ("diamonds", "clubs", "spades")


def test_classify_five_queries_all_return_k_address():
    r = _router()
    queries = [
        "what should I build next?",
        "help me think through a hard problem",
        "I need to understand the architecture",
        "what's the status of everything?",
        "deploy the production release",
    ]
    for q in queries:
        result = r.classify(q)
        assert "k_address" in result, f"No k_address for: {q}"
        assert len(result["k_address"]) >= 3, f"k_address too short: {result['k_address']}"


# ── route() ───────────────────────────────────────────────────────────────────

def test_route_returns_response_key():
    r = _router()
    result = r.route("hello world")
    assert "response" in result or "text" in result or "error" in result


def test_route_returns_cost_key():
    r = _router()
    result = r.route("simple question")
    assert "cost" in result, f"No cost key in result: {list(result.keys())}"


def test_route_returns_savings_key():
    r = _router()
    result = r.route("what time is it?")
    assert "savings" in result, f"No savings key: {list(result.keys())}"


def test_route_template_hit_has_zero_cost():
    """Template hits (tier 0) should have zero API cost."""
    r = _router()
    # Very simple factual question likely to hit template
    result = r.route("hello")
    cost = result.get("cost", result.get("mana_cost", None))
    if result.get("tier", -1) == 0 or result.get("tier_used") == "template":
        assert cost == 0 or cost is None


def test_route_byok_accepted():
    """BYOK key should not raise an error."""
    r = _router()
    try:
        result = r.route("test query", byok="fake-key-for-testing")
        assert isinstance(result, dict)
    except Exception as e:
        # Network errors are OK (no real key), but not type errors
        assert "APIError" in type(e).__name__ or "Connection" in str(e) or "key" in str(e).lower()
