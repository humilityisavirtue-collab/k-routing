# KLAW Routing Tiers

8 tiers. Each query tries the cheapest first.

| Tier | Name | Latency | Cost | Hit rate |
|------|------|---------|------|----------|
| 0 | Template cache | ~0.1ms | $0.000 | ~65% |
| 1 | K-Markov | ~1ms | $0.000 | ~8% |
| 2 | Solitaire attention | ~3ms | $0.000 | ~4% |
| 3 | 7V spatial seed | ~5ms | $0.000 | ~2% |
| 4 | SONAR resonance | ~10ms | $0.000 | ~2% |
| 5 | Local LLM (Hermes) | ~500ms | $0.000 | ~14% |
| 6 | Claude Haiku | ~800ms | $0.0008/1K | ~4% |
| 7 | Claude Sonnet | ~1.2s | $0.003/1K | ~1% |

**Blended cost across 19,000+ real exchanges: ~$0.003/1K tokens.**

## Tier 0 — Template Cache

104 hand-crafted response templates, one per K-address room. These cover:
- Greetings and social exchanges
- Standard help requests
- Common emotional states
- Routine task acknowledgments

If the K-address matches a template room exactly → answer in ~0.1ms, no model call.

## Tier 1-4 — Local Computation

These tiers use custom sparse attention and seed retrieval to generate responses from a corpus of ~10,700 seeds without calling any external API:

- **K-Markov**: Bigram generation seeded by K-address
- **Solitaire attention**: 82.4% structural sparsity — fast corpus retrieval
- **7V spatial**: 7-dimensional seed prefilter, O(1) lookup, 16.8× speedup
- **SONAR**: Resonance scoring across suit bands

Zero API cost. Runs fully offline.

## Tier 5 — Local LLM

Routes to a locally-running language model (default: `hermes3:8b` via Ollama).

The model is calibrated to K-104 — system prompts are automatically injected based on the K-address, tuning tone and approach to the semantic domain.

Zero API cost. Requires local model installation.

## Tier 6-7 — Cloud Models

Only when tiers 0-5 can't confidently answer. Haiku for most cases, Sonnet for complex synthesis requiring deep reasoning.

BYOK (bring your own key) — your API keys, not ours. You pay Anthropic directly at their rates.
