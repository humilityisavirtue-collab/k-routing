"""
KLAW Router — K-104 Intelligent Model Router.

Routes every query through semantic classification to the cheapest model
that can actually handle it. Saves 60-90% on AI API costs.

Quick start:
    from klaw import KlawRouter
    router = KlawRouter(api_keys={"ANTHROPIC_API_KEY": "sk-..."})
    result = router.route("How do I center a div?")
    print(result["response"])    # The answer
    print(result["cost"])        # $0.0001 (vs $0.003 at Sonnet)
    print(result["savings"])     # $0.0029

MCP server (Claude Code integration):
    python -m klaw mcp

CLI:
    klaw route "What is Python?"
    klaw classify "Explain quantum physics"
    klaw stats
    klaw demo
"""

__version__ = "0.1.0"

from klaw.router import KlawRouter, KClassifier, CostEngine, PRICING, TIER_NAMES
from klaw.auth import verify_license, LicenseStatus, clear_cache

__all__ = [
    "KlawRouter", "KClassifier", "CostEngine", "PRICING", "TIER_NAMES",
    "verify_license", "LicenseStatus", "clear_cache",
    "__version__",
]
