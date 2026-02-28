"""
KLAW Router CLI — K-104 Intelligent Model Router.

Usage:
    python -m klaw route "How do I center a div?"
    python -m klaw classify "Explain quantum physics"
    python -m klaw stats
    python -m klaw demo
    python -m klaw mcp          # Start MCP server (for Claude Code)
    python -m klaw setup        # Show setup instructions
"""

import json
import sys


def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = sys.argv[1:]
    if not args:
        print(__doc__.strip())
        return

    cmd = args[0]

    if cmd == "mcp":
        from klaw.mcp_server import main as mcp_main
        mcp_main()

    elif cmd == "setup":
        print_setup()

    elif cmd == "route":
        query = " ".join(args[1:]) if len(args) > 1 else ""
        if not query:
            print("Usage: klaw route 'your query here'")
            return
        from klaw.router import KlawRouter
        router = KlawRouter()
        result = router.route(query)
        print(f"\n  {result['response']}\n")
        print(f"  Model:   {result['model_label']}")
        print(f"  Tier:    {result['tier_name']} ({result['tier']})")
        print(f"  Cost:    ${result['cost']:.6f}")
        print(f"  Saved:   ${result['savings']:.6f}")
        print(f"  Latency: {result['latency_ms']}ms")
        if result.get("error"):
            print(f"  Error:   {result['error']}")
        print()

    elif cmd == "classify":
        query = " ".join(args[1:]) if len(args) > 1 else ""
        if not query:
            print("Usage: klaw classify 'your query here'")
            return
        from klaw.router import KlawRouter, TIER_NAMES
        router = KlawRouter()
        c = router.classify(query)
        print(json.dumps({
            **c,
            "tier_name": TIER_NAMES.get(c["tier"], "?"),
            "template_response": "(exists)" if c.get("template_response") else None,
        }, indent=2, default=str))

    elif cmd == "stats":
        from klaw.router import KlawRouter
        router = KlawRouter()
        stats = router.stats()
        print(f"\n  {'='*50}")
        print(f"  KLAW ROUTER USAGE STATS")
        print(f"  {'='*50}")
        print(f"  Total queries:     {stats['total_queries']}")
        print(f"  Total cost:        ${stats['total_cost']:.4f}")
        print(f"  Total savings:     ${stats['total_savings']:.4f}")
        print(f"  Savings ratio:     {stats['savings_ratio']*100:.1f}%")
        print(f"  Avg cost/query:    ${stats['avg_cost_per_query']:.6f}")
        print(f"  Today cost:        ${stats['daily_cost']:.4f}")
        print(f"  Today queries:     {stats['daily_queries']}")
        print(f"  Tier distribution: {stats.get('tier_percentages', {})}")
        print()

    elif cmd == "demo":
        from klaw.router import KlawRouter, TIER_NAMES, PRICING, select_model
        router = KlawRouter()
        queries = [
            "What is Python?",
            "Write a function to sort a list",
            "Explain the architectural implications of microservices vs monolith",
            "Hi",
            "Compare React, Vue, and Svelte for a PWA",
            "Fix this: for i in range(10) print(i)",
            "Write a haiku about programming",
            "Design a database schema for multi-tenant SaaS with row-level security",
        ]
        print(f"\n  KLAW ROUTER DEMO -- {len(queries)} queries\n")
        print(f"  {'Query':<55} {'Tier':<12} {'Model':<18} {'Cost':>8} {'Saved':>8}")
        print(f"  {'-'*55} {'-'*12} {'-'*18} {'-'*8} {'-'*8}")

        for q in queries:
            c = router.classify(q)
            tier = min(c["tier"], router.max_tier)
            tier_name = TIER_NAMES.get(tier, "?")
            model = select_model(tier, router.available_keys)
            label = PRICING.get(model, {}).get("label", model)
            est_cost = router.cost.estimate_cost(model, len(q), 500)
            est_base = router.cost.estimate_baseline(len(q), 500)
            est_save = max(0, est_base - est_cost)
            q_short = q[:53] + ".." if len(q) > 55 else q
            print(f"  {q_short:<55} {tier_name:<12} {label:<18} "
                  f"${est_cost:>6.4f} ${est_save:>6.4f}")

        print(f"\n  Baseline: all queries at Sonnet rates")
        print()

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__.strip())


def print_setup():
    """Print setup instructions for users."""
    print("""
  ============================================================
                      KLAW ROUTER SETUP
  ============================================================

  1. Install:
     pip install klaw-router

  2. Set API keys (any combination):
     export ANTHROPIC_API_KEY=sk-ant-...
     export OPENAI_API_KEY=sk-...
     export GEMINI_API_KEY=AI...

  3. Add to Claude Code (.mcp.json):
     {
       "mcpServers": {
         "klaw": {
           "command": "klaw",
           "args": ["mcp"]
         }
       }
     }

  4. Use in Claude Code:
     "Route this through klaw: How do I..."

  CLI usage:
     klaw route "your query"
     klaw classify "your query"
     klaw stats
     klaw demo
  ============================================================
""")


if __name__ == "__main__":
    main()
