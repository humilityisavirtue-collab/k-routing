# KLAW Router

K-104 Intelligent Model Router. Routes AI queries to the cheapest model that can handle them.

## Install

```bash
pip install klaw-router
```

## Quick Start

### As a library

```python
from klaw import KlawRouter

router = KlawRouter(api_keys={"ANTHROPIC_API_KEY": "sk-ant-..."})
result = router.route("How do I center a div?")

print(result["response"])    # The answer
print(result["cost"])        # $0.0001
print(result["savings"])     # $0.0029 (vs Sonnet baseline)
print(result["tier_name"])   # "cheap"
```

### As Claude Code MCP tool

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

### CLI

```bash
klaw route "What is Python?"
klaw classify "Explain quantum physics"
klaw stats
klaw demo
klaw setup
```

## How it works

Every query is classified through K-104 semantic addressing — 4 domains (hearts, spades, diamonds, clubs) x complexity tiers — to determine the minimum capable model:

| Tier | Models | Cost/query |
|------|--------|------------|
| Template | Built-in responses | $0.00 |
| Local/Free | Ollama, OpenRouter free | $0.00 |
| Cheap | Haiku, GPT-4o-mini, Gemini Flash | ~$0.001 |
| Mid | Sonnet, GPT-4o, Gemini Pro | ~$0.01 |
| Premium | Opus, GPT-4 | ~$0.05 |

Spend protection: daily caps, monthly budgets, automatic tier downgrade when approaching limits.

## API keys

Set via environment variables or pass directly:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=AI...
export OPENROUTER_API_KEY=sk-or-...
```

## Testing

```bash
# From the openclaw/ directory
pip install pytest
python -m pytest tests/ -v
```

Tests cover classify() suit/tier detection, k_address generation, and route() cost/savings keys.
All 10 tests run without API keys (template tier = free).

## License

MIT
