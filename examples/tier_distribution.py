"""
tier_distribution.py — Show how queries distribute across tiers.

The core claim: 80% of queries never hit a paid API.
This demo routes 20 varied queries and shows where they land.
"""
from klaw import KlawRouter

router = KlawRouter(api_keys={"ANTHROPIC_API_KEY": "sk-ant-..."})

queries = [
    # Tier 0 — template cache (free, <1ms)
    "hello", "hey", "thanks", "ok got it", "yes",
    # Tier 5 — local model (free, ~500ms)
    "what is memoization", "explain recursion", "what's a closure",
    "how does TCP work", "what is a mutex",
    # Tier 6 — Claude Haiku ($0.0008)
    "find the bug in this code: def fib(n): return fib(n-1)+fib(n-2)",
    "write a Python class for a binary search tree",
    "what are the tradeoffs between REST and GraphQL",
    # Tier 7 — Claude Sonnet (rare, complex synthesis)
    "design a distributed system that handles 1M concurrent users with <10ms p99",
    "novel approach to combining formal verification with neural networks",
]

from collections import Counter
tier_counts = Counter()
total_cost = 0.0

for q in queries:
    r = router.route(q)
    tier_counts[r['tier_name']] += 1
    total_cost += r['cost']

print("Tier distribution:")
for tier, count in sorted(tier_counts.items()):
    pct = count / len(queries) * 100
    print(f"  {tier:<12} {count:>2} queries ({pct:.0f}%)")

print(f"\nTotal cost for {len(queries)} queries: ${total_cost:.4f}")
print(f"vs Opus baseline: ${len(queries) * 0.015:.4f}")
print(f"Savings: {(1 - total_cost / (len(queries) * 0.015)) * 100:.0f}%")
