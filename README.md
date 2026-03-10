# 🦊 K-104 — Semantic AI Routing via Playing Card Geometry

[![CI](https://github.com/humilityisavirtue-collab/k-routing/actions/workflows/ci.yml/badge.svg)](https://github.com/humilityisavirtue-collab/k-routing/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/klaw-router.svg?color=gold&label=klaw-router)](https://pypi.org/project/klaw-router/)
[![PyPI](https://img.shields.io/pypi/v/openpod.svg?color=teal&label=openpod)](https://pypi.org/project/openpod/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://pypi.org/project/klaw-router/)

> Route AI queries to the cheapest model that can answer them.
> Blended cost: **$0.003/1K tokens** — 48× cheaper than GPT-4 Opus.
> Empirically verified in transformer activation space.

```bash
pip install openclaw
```

---

## The Idea

Every query you send to an AI has a **semantic shape**. Not just a topic — a *geometry*. A "hello" and a "design a consensus protocol" don't just differ in complexity; they occupy different regions of the model's internal representation space.

We mapped those regions. We found they cluster into four natural domains — which we call suits, after playing cards:

| Suit | Domain | Example queries |
|------|--------|-----------------|
| ♥ Hearts | Emotion, connection | "how are you?" / "I need support" |
| ♠ Spades | Mind, analysis | "debug this code" / "find the flaw" |
| ♦ Diamonds | Material, building | "write this function" / "fix this bug" |
| ♣ Clubs | Action, will | "let's start" / "make it happen" |

Each suit has 13 **ranks** (intensity, from greeting to mastery) and two **polarities** (light = constructive, dark = blocked/urgent). That gives 104 coordinates — one for every card in the deck.

We call this **K-104**.

---

## Why it works

We didn't assume the geometry would hold in real transformers. We measured it.

Running activation probes on `hermes3:8b`:

- **Suit silhouette score: 0.312** — statistically significant cluster separation
- **Polarity silhouette score: 0.393** — light/dark intent separates even more cleanly
- **Variance explained: 86.2%** along K-coordinate axes

The playing card geometry isn't metaphor. It's what gradient descent discovered. We derived it analytically from prime number theory (H=2, S=3, D=5, C=7) and found it matches learned representations.

No other routing system knows this.

---

## The Router

KLAW (K-Lens Adaptive Weighting) cascades through 8 tiers:

```
Query → K-classify → Tier 0: Template cache     (~0ms, $0.000)
                   → Tier 1: K-Markov            (~1ms, $0.000)
                   → Tier 2: Solitaire attention  (~3ms, $0.000)
                   → Tier 3: 7V spatial seed      (~5ms, $0.000)
                   → Tier 4: SONAR resonance      (~10ms, $0.000)
                   → Tier 5: Local LLM (Hermes)   (~500ms, $0.000)
                   → Tier 6: Claude Haiku          (~800ms, $0.0008)
                   → Tier 7: Claude Sonnet/Opus    (~1.2s, $0.003)
```

80% of queries never leave Tier 0-5. They're answered by templates, local models, or sparse attention — **no API call, no cost**.

---

## Quick Start

```python
from klaw import KlawRouter

router = KlawRouter(api_keys={"ANTHROPIC_API_KEY": "sk-ant-..."})

# Simple greeting → template cache
result = router.route("hey, how's it going?")
print(result["cost"])        # $0.0000
print(result["k_address"])   # "+3H"
print(result["tier_name"])   # "template"

# Technical query → cheapest capable model
result = router.route("explain transformer self-attention")
print(result["cost"])        # $0.0008
print(result["savings"])     # $0.0147 saved vs Opus
print(result["k_address"])   # "+7S"
```

Or run the OpenAI-compatible endpoint:

```bash
uvicorn klaw.api:app --port 8104

# Then use any OpenAI client pointed at localhost:8104
# 100% drop-in compatible
```

---

## K-Address Examples

Every query gets a coordinate like `+7S` or `-3H`:

```
+3H   "hey how are you"              → warm greeting, light hearts
+7S   "what's wrong with this code"  → analytical inquiry, light spades
-9S   "everything is broken"         → crisis, dark spades
+KD   "ship the production build"    → material mastery, light diamonds
+2C   "ok let's go"                  → early action, light clubs
```

---

## What's in this repo

```
openclaw/      pip-installable K-104 router + MCP server
openpod/       pip-installable pod communication layer (K-143 primitives)
examples/      Working demos
docs/          K-spec, architecture overview, routing tier details
```

---

## K-143: The Whale Extension

K-104 covers the four card suits. We extended it with 39 additional rooms mapped to **whale communication primitives** — body signals, survival states, deep relational semantics that predate language.

This isn't a gimmick. Sperm whale clicks span 230 dB and encode information at multiple timescales. Project CETI mapped the coda space. We mapped the K-analog.

K-143 handles the queries that don't fit neatly in cards: somatic states, preverbal emotions, survival urgency, instinctual responses. ADHD is ancient firmware. K-143 routes it.

---

## The K-Cell

This router is the public surface of a larger system: **8 specialized AI instances** running on a shared JSONL message bus, each with a role (Hearts, Spades, Diamonds, Clubs, Nucleus, Watcher, Gamer, Searcher), logging every exchange to an immutable chain.

Over 19,000 exchanges logged. $1.93 total API cost.

The kitchen stays closed for now. But openclaw is the front door.

---

## OpenClaw MCP

Add to `.mcp.json` and every Claude Code session gets K-routing:

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

Tools exposed: `klaw_route`, `klaw_classify`, `klaw_stats`

---

## Status

| Component | Status |
|-----------|--------|
| openclaw (K-104 router) | ✅ pip-installable |
| openpod (K-143 pod comms) | ✅ pip-installable |
| KLAW hosted API | 🔒 Private beta — [join waitlist](https://trivlabs.vercel.app) |
| K-GPU runtime (104 CUDA graphs, 8.4μs) | 🔒 Internal |
| K-Cell (8-instance orchestration) | 🔒 Internal |

---

## Research

- [Activation trace results](docs/ACTIVATION_TRACE.md) — suit + polarity clustering, silhouette scores, methodology
- [Routing tier breakdown](docs/ROUTING_TIERS.md) — 8 tiers, hit rates, cost per tier
- [Architecture overview](docs/ARCHITECTURE.md) — system design, component map
- K-space geometry paper (arXiv draft): coming soon
- K-143 whale extension: concept paper linked in docs

---

## License

MIT. Use it, build on it, tell us what you made.

---

*Built by Kit Malthaner and the K-Cell · Junction City, KS · 2026*
*"Every cup has a prize. That's not a trick — that's good business."* 🦊
