"""
klaw_streamer.py -- SSE streaming for KLAW UFO.

Provides functions for creating streaming responses in the OpenAI format.
Handles both fake streaming (for corpus hits) and real streaming (for Hermes/Claude).
"""

import asyncio
import json
from typing import Dict, AsyncGenerator, Optional

try:
    from fastapi.responses import StreamingResponse
except ImportError:
    StreamingResponse = None  # type: ignore

try:
    import httpx as _httpx
except ImportError:
    _httpx = None

OLLAMA_URL = "http://localhost:11434/api/generate"


# ---------------------------------------------------------------------------
# Real Hermes streaming (canonical — used by klaw_api.py)
# ---------------------------------------------------------------------------

async def hermes_stream(
    query: str,
    system_prompt: str = "You are a helpful AI assistant. Be concise.",
    k_address: str = "",
    model: str = "hermes3:8b",
) -> AsyncGenerator[str, None]:
    """Stream tokens from Ollama generate API as they arrive. Yields raw token strings.

    Falls back to a single-shot yield if httpx is not installed or Ollama is unreachable.
    """
    if _httpx is None:
        yield query  # fallback — caller handles trickle
        return

    try:
        async with _httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", OLLAMA_URL, json={
                "model": model,
                "system": system_prompt,
                "prompt": query,
                "stream": True,
            }) as r:
                async for line in r.aiter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
    except Exception:
        # If Ollama unreachable, yield nothing — caller will trickle cached result
        return


# ---------------------------------------------------------------------------
# Streaming response creation
# ---------------------------------------------------------------------------

def create_streaming_response(
    result: Dict,
    tier_used: str,
    mana_cost: int,
    mana_remaining: int,
    k_address: str,
    confidence: float,
    template_id: str,
    latency_ms: int,
) -> "StreamingResponse":
    """Create a streaming response based on the result.

    Corpus/template tiers → fake_stream (trickle pre-built response).
    Hermes tiers → real_hermes_sse_stream (live Ollama tokens).
    """
    if StreamingResponse is None:
        raise RuntimeError("fastapi is required for create_streaming_response")

    is_hermes = "hermes" in tier_used.lower() and _httpx is not None
    if is_hermes:
        return StreamingResponse(
            real_hermes_sse_stream(
                result["response"],
                tier_used,
                mana_cost,
                mana_remaining,
                k_address,
                confidence,
                template_id,
                latency_ms,
            ),
            media_type="text/event-stream",
        )
    else:
        return StreamingResponse(
            fake_stream(
                result["response"],
                tier_used,
                mana_cost,
                mana_remaining,
                k_address,
                confidence,
                template_id,
                latency_ms,
            ),
            media_type="text/event-stream",
        )


# ---------------------------------------------------------------------------
# Fake streaming for corpus hits
# ---------------------------------------------------------------------------

async def fake_stream(
    response: str,
    tier_used: str,
    mana_cost: int,
    mana_remaining: int,
    k_address: str,
    confidence: float,
    template_id: str,
    latency_ms: int,
) -> AsyncGenerator[str, None]:
    """Chunk the assembled response and yield SSE chunks."""
    chunk_size = 32  # Adjust as needed
    for i in range(0, len(response), chunk_size):
        chunk = response[i:i + chunk_size]
        data = {
            "choices": [
                {
                    "delta": {
                        "content": chunk
                    },
                    "finish_reason": None,
                    "index": 0
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "tier_used": tier_used,
            "mana_cost": mana_cost,
            "mana_remaining": mana_remaining,
            "k_address": k_address,
            "confidence": confidence,
            "template_id": template_id,
            "latency_ms": latency_ms,
        }
        yield f"data: {json.dumps(data)}\n\n"
        await asyncio.sleep(0.008)

    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Real Hermes streaming — SSE-formatted (wraps hermes_stream for direct use)
# ---------------------------------------------------------------------------

async def real_hermes_sse_stream(
    cached_response: str,
    tier_used: str,
    mana_cost: int,
    mana_remaining: int,
    k_address: str,
    confidence: float,
    template_id: str,
    latency_ms: int,
    query: str = "",
    system_prompt: str = "You are a helpful AI assistant. Be concise.",
    model: str = "hermes3:8b",
) -> AsyncGenerator[str, None]:
    """Stream live Hermes tokens in KLAW SSE format.

    If httpx is available and a query is provided, streams real tokens from Ollama.
    Falls back to fake_stream (trickle the cached_response) if httpx unavailable.
    """
    base_meta = {
        "tier_used": tier_used,
        "mana_cost": mana_cost,
        "mana_remaining": mana_remaining,
        "k_address": k_address,
        "confidence": confidence,
        "template_id": template_id,
        "latency_ms": latency_ms,
    }

    if _httpx is None or not query:
        # Fallback: trickle the pre-built response
        async for chunk in fake_stream(
            cached_response, tier_used, mana_cost, mana_remaining,
            k_address, confidence, template_id, latency_ms,
        ):
            yield chunk
        return

    got_tokens = False
    async for token in hermes_stream(query, system_prompt, k_address, model):
        got_tokens = True
        data = {
            "choices": [{"delta": {"content": token}, "finish_reason": None, "index": 0}],
            **base_meta,
        }
        yield f"data: {json.dumps(data)}\n\n"

    if not got_tokens:
        # Ollama unreachable — fall back to trickle
        async for chunk in fake_stream(
            cached_response, tier_used, mana_cost, mana_remaining,
            k_address, confidence, template_id, latency_ms,
        ):
            yield chunk
        return

    yield "data: [DONE]\n\n"