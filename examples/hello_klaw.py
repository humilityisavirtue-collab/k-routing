"""
hello_klaw.py — K-104 routing in 10 lines.

Install: pip install openclaw
"""
from klaw import KlawRouter

router = KlawRouter(api_keys={"ANTHROPIC_API_KEY": "sk-ant-..."})

queries = [
    "hey, how's it going?",
    "what's wrong with this recursive function?",
    "explain transformer self-attention",
    "design a distributed consensus protocol",
]

for q in queries:
    result = router.route(q)
    print(f"[{result['k_address']}] {q[:45]:<45} → {result['tier_name']:<10} ${result['cost']:.4f}")
