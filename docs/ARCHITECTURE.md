# K-104 Architecture — Overview

> This doc describes the public surface. The full implementation is internal.

## The Routing Cascade

```
User Query
    │
    ▼
K-Classifier  ──────────────────────────────────────────────
    │                                                        │
    │  K-address: +7S (Spades, rank 7, light)               │
    ▼                                                        │
┌───────────────────────────────┐                           │
│  TIER 0: Template Cache       │ ← ~80% of queries         │
│  104 pre-written room texts   │   0ms, $0.000             │
│  Exact K-address match        │                           │
└───────────┬───────────────────┘                           │
            │ miss                                          │
            ▼                                              K-address
┌───────────────────────────────┐              (suit/rank/polarity)
│  TIER 1-4: Local Computation  │                           │
│  K-Markov, Solitaire, 7V,     │ ← ~15% of queries        │
│  SONAR sparse attention       │   1-10ms, $0.000          │
└───────────┬───────────────────┘                           │
            │ miss                                          │
            ▼                                              ◄─┘
┌───────────────────────────────┐
│  TIER 5: Local LLM            │ ← ~4% of queries
│  hermes3:8b (or similar)      │   ~500ms, $0.000
│  Runs fully offline           │
└───────────┬───────────────────┘
            │ miss
            ▼
┌───────────────────────────────┐
│  TIER 6: Claude Haiku         │ ← ~0.9% of queries
│  Fast, cheap cloud model      │   ~800ms, $0.0008
└───────────┬───────────────────┘
            │ miss (complex synthesis only)
            ▼
┌───────────────────────────────┐
│  TIER 7: Claude Sonnet/Opus   │ ← ~0.1% of queries
│  Full reasoning when needed   │   ~1.2s, $0.003
└───────────────────────────────┘
```

## The K-Classifier

Assigns every query a **K-address** — a 3-component coordinate:

```
+7S = polarity(+) rank(7) suit(S)
       light      intense  Spades(analysis)
```

**Suits** (semantic domains):
- ♥ Hearts — emotion, connection, relationship
- ♠ Spades — analysis, logic, truth-seeking
- ♦ Diamonds — material, building, implementation
- ♣ Clubs — action, will, energy, momentum

**Rank** (1-13): intensity/depth of the query
**Polarity** (+/-): constructive (light) or blocked/urgent (dark)

Classification runs in microseconds using centroid matching against a 104-point manifold.

## Why 104?

4 suits × 13 ranks × 2 polarities = 104.

The prime number encoding (H=2, S=3, D=5, C=7) was derived analytically. When we probed transformer activations, we found:

- Suit cluster silhouette score: **0.312**
- Polarity silhouette score: **0.393**
- Variance explained by K-axes: **86.2%**

The geometry isn't imposed — it's what models learn.

## Deployment Modes

**Library mode:**
```python
from klaw import KlawRouter
router = KlawRouter(api_keys={...})
result = router.route("your query")
```

**API mode (OpenAI-compatible):**
```bash
uvicorn klaw.api:app --port 8104
# POST /v1/chat/completions — drop-in replacement
```

**MCP mode (Claude Code integration):**
```json
{"mcpServers": {"klaw": {"command": "klaw", "args": ["mcp"]}}}
```
