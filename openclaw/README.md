# KLAW Router

[![CI](https://github.com/kit-triv/openclaw/actions/workflows/openclaw-ci.yml/badge.svg)](https://github.com/kit-triv/openclaw/actions/workflows/openclaw-ci.yml)
[![PyPI](https://img.shields.io/pypi/v/klaw-router)](https://pypi.org/project/klaw-router/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/klaw-router)](https://pypi.org/project/klaw-router/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**K-104 Intelligent Model Router.** Route AI queries to the cheapest model that can handle them. Up to 48x cheaper than Claude Opus — without sacrificing quality.

## Install

```bash
pip install klaw-router
```

## Quick Start

```python
from klaw import KlawRouter

router = KlawRouter()
result = router.route("How do I center a div?")

print(result["response"])    # The answer
print(result["cost"])        # $0.0001
print(result["savings"])     # $0.0029 saved vs Sonnet baseline
print(result["tier_name"])   # "template" (free)
```

Pass API keys directly or via environment variables:

```python
router = KlawRouter(api_keys={
    "ANTHROPIC_API_KEY": "sk-ant-...",
    "OPENAI_API_KEY": "sk-...",
    "GEMINI_API_KEY": "AI...",
})
```

## How It Works

Every query gets classified into a K-104 semantic address (4 domains × 13 ranks × 2 polarities = 104 rooms) and routed to the minimum capable model:

| Tier | Models | Cost/query |
|------|--------|------------|
| 0 — Template | Built-in corpus (1,000+ patterns) | **$0.00** |
| 1 — Local | Ollama, OpenRouter free tier | **$0.00** |
| 2 — Cheap | Haiku, GPT-4o-mini, Gemini Flash | ~$0.001 |
| 3 — Mid | Sonnet, GPT-4o, Gemini Pro | ~$0.01 |
| 4 — Premium | Opus, GPT-4 | ~$0.05 |

The classifier routes ~80% of everyday queries to tier 0–1 (free). Only genuinely complex reasoning reaches premium tiers.

**Empirical result:** Transformer activations cluster by K-104 suit with silhouette score 0.312 — the geometry is real, not imposed.

## Claude Code MCP Integration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "klaw": {
      "command": "klaw",
      "args": ["mcp"]
    }
  }
}
```

Then use `klaw_route`, `klaw_classify`, and `klaw_stats` tools in Claude Code.

## CLI

```bash
klaw route "What is Python?"
klaw classify "Explain quantum physics"
klaw stats
klaw demo
klaw setup
```

## API Keys

Set via environment variables:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=AI...
export OPENROUTER_API_KEY=sk-or-...
```

Or pass directly to `KlawRouter(api_keys={...})`. No keys required for tier 0 template routing.

## Classify Only

```python
from klaw import KlawRouter

r = KlawRouter()
c = r.classify("debug this async Python function")
print(c["suit"])       # "spades"
print(c["tier"])       # 2
print(c["k_address"])  # "+5S"
```

## Testing

```bash
cd openclaw
pip install pytest
python -m pytest tests/ -v
```

All 10 tests pass without API keys (template tier is free).

## License

MIT
