# Contributing to K-104

Thanks for looking. Here's how this works.

---

## What we're building

K-104 is a semantic routing layer for AI queries. The goal is: every query goes to the cheapest model that can answer it well. 80% should never reach an API at all.

If you want to help with that, read on.

---

## Ways to contribute

### 1. Corpus seeds

The template layer (Tier 0) is a set of ~10,700 seed responses, one or more per K-address room. Better seeds = better zero-cost responses.

Add seeds to `openclaw/src/klaw/seeds/` as `.speech` files. Format:

```
K: +3H
---
Hey, good to hear from you. What's on your mind?
```

Good seeds are:
- Brief (under 80 words)
- Warm without being hollow
- Actual answers, not hedges

### 2. Classifier improvements

The K-104 classifier (`openclaw/src/klaw/router.py → KClassifier`) uses keyword centroids. If you have better ways to classify query → suit/rank/polarity (embeddings, fine-tuned probe, etc.), we want to hear it.

We already have silhouette scores from activation probes to benchmark against (see `docs/ACTIVATION_TRACE.md`). Beat 0.312 suit silhouette on the same 104-prompt test set and we'll merge it.

### 3. Backend adapters

`KlawRouter` supports Anthropic, OpenAI, Gemini, and Ollama. Adding a new backend:

1. Add a method `_call_[backend](prompt, model, options) -> dict` in `router.py`
2. Add the backend to the `BACKENDS` mapping
3. Write a test in `tests/test_router.py`
4. PR with a note on what model you tested against

### 4. openpod channel adapters

`openpod` handles pod communication (JSONL bus, priority queue, KCoda encoding). We need channel adapters for Telegram, Discord, and ntfy. Adapter interface:

```python
class ChannelAdapter:
    async def send(self, message: str) -> None: ...
    async def receive(self) -> AsyncIterator[str]: ...
```

### 5. Bug reports and test cases

If `router.route(query)` gives you the wrong tier, open an issue with:
- The query
- What tier you got
- What tier you expected
- Why (even informal reasoning helps)

We'll add it as a test case.

---

## Development setup

```bash
git clone https://github.com/humilityisavirtue-collab/k-routing.git
cd k-routing

# openclaw
cd openclaw
pip install -e ".[crypto]"
pip install pytest
python -m pytest tests/ -v

# openpod
cd ../openpod
pip install -e .
python -c "from openpod import Pod; print('ok')"
```

---

## What we're not looking for

- Rewrites for their own sake
- Dependencies that add weight without adding capability
- Features that optimize for benchmark numbers rather than real query cost reduction

The codebase is deliberately lean. Adding complexity has a cost.

---

## Licensing

Contributions go under MIT (same as the repo). You keep your copyright, we keep the project open.

---

*Questions? Open an issue. We read them.*
