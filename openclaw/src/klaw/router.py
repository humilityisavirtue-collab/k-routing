"""
KLAW Router Core — Standalone K-104 intelligent model routing.

No external dependencies. Self-contained classifier using K-104
semantic addressing.
"""

import json
import os
import re
import time
import hashlib
import struct
import zlib
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════
# PRICING & TIERS
# ═══════════════════════════════════════════════════════════

PRICING = {
    # Free tier
    "template":         {"input": 0,     "output": 0,     "tier": 0, "label": "K-Template"},
    # Local/Free
    "ollama_local":     {"input": 0,     "output": 0,     "tier": 1, "label": "Ollama Local"},
    "openrouter_free":  {"input": 0,     "output": 0,     "tier": 1, "label": "OpenRouter Free"},
    # Cheap
    "haiku":            {"input": 0.80,  "output": 4.00,  "tier": 2, "label": "Claude Haiku"},
    "gpt4o_mini":       {"input": 0.15,  "output": 0.60,  "tier": 2, "label": "GPT-4o-mini"},
    "gemini_flash":     {"input": 0.075, "output": 0.30,  "tier": 2, "label": "Gemini Flash"},
    # Mid
    "sonnet":           {"input": 3.00,  "output": 15.00, "tier": 3, "label": "Claude Sonnet"},
    "gpt4o":            {"input": 5.00,  "output": 15.00, "tier": 3, "label": "GPT-4o"},
    "gemini_pro":       {"input": 1.25,  "output": 5.00,  "tier": 3, "label": "Gemini Pro"},
    # Premium
    "opus":             {"input": 15.00, "output": 75.00, "tier": 4, "label": "Claude Opus"},
    "gpt4":             {"input": 30.00, "output": 60.00, "tier": 4, "label": "GPT-4"},
}

DEFAULT_BASELINE = "sonnet"

TIER_NAMES = {0: "template", 1: "local/free", 2: "cheap", 3: "mid", 4: "premium"}

TIER_MODELS = {
    0: ["template"],
    1: ["ollama_local", "openrouter_free"],
    2: ["gemini_flash", "gpt4o_mini", "haiku"],
    3: ["gemini_pro", "sonnet", "gpt4o"],
    4: ["opus", "gpt4"],
}

# K-104 suit domain keywords for classification
SUIT_KEYWORDS = {
    "hearts": {
        "love", "feel", "emotion", "relationship", "friend", "family", "care",
        "empathy", "connection", "trust", "grateful", "lonely", "sad", "happy",
        "hurt", "kind", "forgive", "miss", "bond", "intimacy", "compassion",
        "jealous", "affection", "warmth", "loss", "grief", "joy", "partner",
    },
    "spades": {
        "think", "analyze", "reason", "logic", "truth", "understand", "explain",
        "compare", "evaluate", "argument", "debate", "prove", "theory", "why",
        "paradox", "conflict", "strategy", "puzzle", "riddle", "solve", "math",
        "philosophy", "science", "research", "hypothesis", "evidence", "mind",
    },
    "diamonds": {
        "build", "make", "create", "code", "implement", "deploy", "ship",
        "money", "budget", "cost", "price", "material", "body", "health",
        "food", "exercise", "house", "tool", "fix", "repair", "construct",
        "practical", "concrete", "tangible", "physical", "hardware", "craft",
    },
    "clubs": {
        "do", "act", "start", "launch", "push", "move", "energy", "will",
        "power", "force", "drive", "motivation", "initiative", "bold",
        "courage", "dare", "fight", "challenge", "compete", "win", "lead",
        "decide", "commit", "execute", "hustle", "grind", "ambition",
    },
}


# ═══════════════════════════════════════════════════════════
# CLAW RUNTIME (decrypt rooms.claw)
# ═══════════════════════════════════════════════════════════

_K_SEED_MATERIAL = (
    b"104_rooms_4_suits_13_ranks_2_polarities"
    b"_dai_stiho_guard_growth_ease_pain"
    b"_L+K+T=C_light_speed"
)

def _derive_key() -> bytes:
    salt = b"openclaw_k104_" + hashlib.sha256(b"kit.triv").digest()[:16]
    return hashlib.pbkdf2_hmac("sha256", _K_SEED_MATERIAL, salt, iterations=100_000)

def _decrypt(blob: bytes, key: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = blob[:12]
        ct = blob[12:]
        return AESGCM(key).decrypt(nonce, ct, None)
    except ImportError:
        pass
    # Fallback XOR stream
    nonce = blob[:32]
    tag = blob[32:48]
    encrypted = blob[48:]
    expected_tag = hashlib.sha256(key + nonce + encrypted).digest()[:16]
    if tag != expected_tag:
        raise ValueError("Integrity check failed — wrong key or corrupted .claw file")
    stream_key = hashlib.pbkdf2_hmac("sha256", key, nonce, iterations=1000)
    decrypted = bytearray(len(encrypted))
    for i in range(0, len(encrypted), 32):
        chunk_key = hashlib.sha256(stream_key + i.to_bytes(8, "big")).digest()
        for j in range(min(32, len(encrypted) - i)):
            decrypted[i + j] = encrypted[i + j] ^ chunk_key[j]
    return bytes(decrypted)


class ClawRuntime:
    """Load and query compiled rooms from rooms.claw."""

    def __init__(self, claw_path: str = None):
        if claw_path:
            self.path = Path(claw_path)
        else:
            # Look for rooms.claw bundled with the package
            self.path = Path(__file__).parent / "rooms.claw"
        self._data = None
        if self.path.exists():
            self._load()

    def _load(self):
        with open(self.path, "rb") as f:
            magic = f.read(4)
            if magic != b"CLAW":
                raise ValueError(f"Not a .claw file: {self.path}")
            _version = struct.unpack("<H", f.read(2))[0]
            blob = f.read()
        key = _derive_key()
        compressed = _decrypt(blob, key)
        raw = zlib.decompress(compressed)
        self._data = json.loads(raw.decode("utf-8"))

    @property
    def loaded(self) -> bool:
        return self._data is not None

    @property
    def room_count(self) -> int:
        return self._data.get("room_count", 0) if self._data else 0

    def get(self, room_id: str) -> Optional[dict]:
        if not self._data:
            return None
        return self._data.get("rooms", {}).get(room_id)

    def search(self, keyword: str) -> list:
        if not self._data:
            return []
        kw = keyword.lower()
        results = []
        for trigger, room_ids in self._data.get("trigger_index", {}).items():
            if kw in trigger:
                results.extend(room_ids)
        return list(set(results))

    def list_rooms(self) -> list:
        if not self._data:
            return []
        return sorted(self._data.get("rooms", {}).keys())


# ═══════════════════════════════════════════════════════════
# K-104 CLASSIFIER (standalone)
# ═══════════════════════════════════════════════════════════

class KClassifier:
    """Classify queries using K-104 semantic addressing."""

    def __init__(self):
        self._rooms = ClawRuntime()

    def classify(self, query: str) -> dict:
        query_lower = query.lower().strip()
        word_count = len(query.split())
        words = set(query_lower.split())

        # Greetings → tier 0 (free template)
        greetings = {"hi", "hello", "hey", "yo", "sup", "thanks", "bye",
                     "good morning", "good night", "gm", "gn"}
        if query_lower in greetings:
            template_resp = self._get_greeting_response(query_lower)
            return {
                "tier": 0,
                "suit": "hearts",
                "polarity": "light",
                "confidence": 0.95,
                "reason": "greeting_template",
                "template_response": template_resp,
                "k_address": "+H",
            }

        # Suit classification via keyword matching
        suit = self._classify_suit(words)

        # Polarity detection
        dark_words = {"stuck", "frustrated", "overwhelmed", "confused", "angry",
                      "broken", "error", "bug", "fail", "crash", "wrong", "help",
                      "anxious", "scared", "lost", "hopeless", "struggling"}
        light_words = {"excited", "happy", "good", "great", "thanks", "working",
                       "done", "love", "nice", "cool", "awesome", "perfect",
                       "grateful", "confident", "inspired", "ready"}
        if words & dark_words:
            polarity = "dark"
        elif words & light_words:
            polarity = "light"
        else:
            polarity = "neutral"

        # Tier by complexity
        tier, confidence, reason = self._assess_complexity(query_lower, word_count, suit, words)

        pol_char = "+" if polarity == "light" else "-" if polarity == "dark" else "?"
        return {
            "tier": tier,
            "suit": suit,
            "polarity": polarity,
            "confidence": confidence,
            "reason": reason,
            "template_response": None,
            "k_address": f"{pol_char}{suit[0].upper()}",
        }

    def _classify_suit(self, words: set) -> str:
        scores = {}
        for suit, keywords in SUIT_KEYWORDS.items():
            overlap = len(words & keywords)
            if overlap > 0:
                scores[suit] = overlap
        if scores:
            return max(scores, key=scores.get)
        return "spades"  # default: analytical

    def _get_greeting_response(self, greeting: str) -> str:
        responses = {
            "hi": "Hello! How can I help you today?",
            "hello": "Hello! What can I do for you?",
            "hey": "Hey! What's up?",
            "yo": "Yo! What do you need?",
            "sup": "Not much! What can I help with?",
            "thanks": "You're welcome!",
            "bye": "Take care! Dai stihó.",
            "good morning": "Good morning! Ready to go.",
            "good night": "Good night! Rest well.",
            "gm": "Good morning!",
            "gn": "Good night!",
        }
        return responses.get(greeting, "Hello!")

    def _assess_complexity(self, q: str, word_count: int, suit: str, words: set) -> tuple:
        # Tier 1: Simple/factual/short
        simple_patterns = [
            r"^(what|who|when|where) (is|are|was|were) ",
            r"^(how do (you|i|we)|how to) ",
            r"^(define|meaning of|translate) ",
            r"^(list|name|give me) ",
        ]
        for pattern in simple_patterns:
            if re.match(pattern, q) and word_count < 20:
                return (1, 0.8, "simple_query")

        if word_count < 5:
            return (1, 0.7, "short_query")

        # Tier 2: Standard coding/writing
        coding = {"code", "function", "class", "bug", "error", "fix", "implement",
                  "write", "create", "build", "script", "html", "css", "python",
                  "javascript", "api", "sql", "regex", "test", "debug"}
        writing = {"write", "draft", "email", "letter", "summarize", "rewrite",
                   "edit", "proofread", "translate", "format"}
        if words & coding and word_count < 50:
            return (2, 0.75, "standard_coding")
        if words & writing and word_count < 100:
            return (2, 0.7, "standard_writing")
        if word_count < 30:
            return (2, 0.65, "moderate_query")

        # Tier 3: Complex reasoning
        complex_signals = {"explain", "analyze", "compare", "design", "architect",
                          "refactor", "optimize", "strategy", "debate", "evaluate",
                          "novel", "creative", "story", "essay", "research", "review"}
        if words & complex_signals:
            return (3, 0.7, "complex_reasoning")
        if word_count > 50:
            return (3, 0.6, "long_context")

        # Tier 4: Premium (explicit request only)
        premium_signals = {"opus", "best model", "most accurate", "critical",
                          "production", "security audit", "formal proof"}
        if any(s in q for s in premium_signals):
            return (4, 0.8, "premium_requested")

        return (2, 0.5, "default_cheap")


# ═══════════════════════════════════════════════════════════
# COST ENGINE
# ═══════════════════════════════════════════════════════════

class CostEngine:
    """Track costs, enforce caps, calculate savings."""

    def __init__(self, daily_cap: float = 5.00, monthly_budget: float = 50.00,
                 data_dir: Path = None):
        self.daily_cap = daily_cap
        self.monthly_budget = monthly_budget
        self._data_dir = data_dir or Path.home() / ".klaw"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._usage_file = self._data_dir / "usage.json"
        self._load_usage()

    def _load_usage(self):
        today = date.today().isoformat()
        if self._usage_file.exists():
            try:
                self.usage = json.loads(self._usage_file.read_text(encoding="utf-8"))
                if self.usage.get("today") != today:
                    self.usage["daily_cost"] = 0.0
                    self.usage["daily_queries"] = 0
                    self.usage["today"] = today
                return
            except Exception:
                pass
        self.usage = {
            "today": today,
            "daily_cost": 0.0, "daily_queries": 0,
            "monthly_cost": 0.0, "monthly_queries": 0,
            "total_cost": 0.0, "total_queries": 0,
            "total_savings": 0.0,
            "tier_distribution": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0},
        }

    def _save(self):
        self._usage_file.write_text(json.dumps(self.usage, indent=2), encoding="utf-8")

    def estimate_cost(self, model: str, input_chars: int, output_chars: int) -> float:
        rates = PRICING.get(model, PRICING["sonnet"])
        input_tokens = input_chars / 4.0
        output_tokens = output_chars / 4.0
        return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000

    def estimate_baseline(self, input_chars: int, output_chars: int) -> float:
        return self.estimate_cost(DEFAULT_BASELINE, input_chars, output_chars)

    def can_afford(self, estimated_cost: float) -> tuple:
        if self.usage["daily_cost"] + estimated_cost > self.daily_cap:
            return False, f"Daily cap ${self.daily_cap:.2f} exceeded"
        if self.usage["monthly_cost"] + estimated_cost > self.monthly_budget:
            return False, f"Monthly budget ${self.monthly_budget:.2f} exceeded"
        return True, "ok"

    def max_affordable_tier(self) -> int:
        remaining = self.daily_cap - self.usage["daily_cost"]
        if remaining > 0.10:
            return 4
        if remaining > 0.01:
            return 3
        if remaining > 0.001:
            return 2
        if remaining > 0:
            return 1
        return 0

    def record(self, model: str, input_chars: int, output_chars: int, tier: int) -> dict:
        actual = self.estimate_cost(model, input_chars, output_chars)
        baseline = self.estimate_baseline(input_chars, output_chars)
        savings = max(0, baseline - actual)

        self.usage["daily_cost"] += actual
        self.usage["daily_queries"] += 1
        self.usage["monthly_cost"] += actual
        self.usage["monthly_queries"] += 1
        self.usage["total_cost"] += actual
        self.usage["total_queries"] += 1
        self.usage["total_savings"] += savings
        self.usage["tier_distribution"][str(tier)] = \
            self.usage["tier_distribution"].get(str(tier), 0) + 1
        self._save()

        return {
            "actual_cost": actual,
            "baseline_cost": baseline,
            "savings": savings,
            "daily_remaining": self.daily_cap - self.usage["daily_cost"],
        }

    def get_stats(self) -> dict:
        total_q = max(self.usage["total_queries"], 1)
        dist = self.usage.get("tier_distribution", {})
        return {
            **self.usage,
            "avg_cost_per_query": self.usage["total_cost"] / total_q,
            "avg_savings_per_query": self.usage["total_savings"] / total_q,
            "savings_ratio": self.usage["total_savings"] /
                max(self.usage["total_savings"] + self.usage["total_cost"], 0.001),
            "tier_percentages": {
                TIER_NAMES.get(int(k), k): round(v / total_q * 100, 1)
                for k, v in dist.items() if v > 0
            },
        }


# ═══════════════════════════════════════════════════════════
# BACKENDS
# ═══════════════════════════════════════════════════════════

class Backends:
    """Model backend connections."""

    def __init__(self, api_keys: dict = None):
        self.keys = dict(api_keys or {})
        # Also pull from environment
        for env_key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
                        "OPENROUTER_API_KEY"):
            if env_key not in self.keys:
                val = os.environ.get(env_key, "")
                if val:
                    self.keys[env_key] = val

    def call(self, model: str, query: str, system_prompt: str = "",
             max_tokens: int = 1024) -> dict:
        tier = PRICING.get(model, {}).get("tier", 3)
        if tier == 0:
            return {"response": "(template)", "model": model, "tokens_in": 0, "tokens_out": 0}
        if tier == 1:
            return self._call_local(query, system_prompt, max_tokens)
        if model in ("haiku", "sonnet", "opus"):
            return self._call_anthropic(model, query, system_prompt, max_tokens)
        if model in ("gemini_flash", "gemini_pro"):
            return self._call_gemini(model, query, system_prompt, max_tokens)
        if model in ("gpt4o_mini", "gpt4o", "gpt4"):
            return self._call_openai(model, query, system_prompt, max_tokens)
        if model == "openrouter_free":
            return self._call_openrouter(query, system_prompt, max_tokens)
        return self._call_local(query, system_prompt, max_tokens)

    def _call_local(self, query, system_prompt, max_tokens) -> dict:
        import urllib.request
        try:
            payload = json.dumps({
                "model": "gemma3:4b",
                "messages": [
                    {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                    {"role": "user", "content": query},
                ],
                "stream": False,
                "options": {"num_predict": max_tokens},
            }).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data.get("message", {}).get("content", "")
                return {"response": text, "model": "ollama_local",
                        "tokens_in": len(query) // 4, "tokens_out": len(text) // 4}
        except Exception as e:
            return {"response": f"[Local model unavailable: {e}]", "model": "ollama_local",
                    "tokens_in": 0, "tokens_out": 0, "error": str(e)}

    def _call_anthropic(self, model, query, system_prompt, max_tokens) -> dict:
        import urllib.request
        api_key = self.keys.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return {"response": "[No Anthropic API key]", "model": model,
                    "tokens_in": 0, "tokens_out": 0, "error": "no_key"}
        model_map = {"haiku": "claude-haiku-4-5-20251001", "sonnet": "claude-sonnet-4-6",
                     "opus": "claude-opus-4-6"}
        payload = json.dumps({
            "model": model_map.get(model, model),
            "max_tokens": max_tokens,
            "system": system_prompt or "You are a helpful assistant.",
            "messages": [{"role": "user", "content": query}],
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=payload,
            headers={"Content-Type": "application/json", "x-api-key": api_key,
                     "anthropic-version": "2023-06-01"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = "".join(b.get("text", "") for b in data.get("content", [])
                               if b.get("type") == "text")
                usage = data.get("usage", {})
                return {"response": text, "model": model,
                        "tokens_in": usage.get("input_tokens", len(query) // 4),
                        "tokens_out": usage.get("output_tokens", len(text) // 4)}
        except Exception as e:
            return {"response": f"[Anthropic error: {e}]", "model": model,
                    "tokens_in": 0, "tokens_out": 0, "error": str(e)}

    def _call_gemini(self, model, query, system_prompt, max_tokens) -> dict:
        import urllib.request
        api_key = self.keys.get("GEMINI_API_KEY", "")
        if not api_key:
            return {"response": "[No Gemini API key]", "model": model,
                    "tokens_in": 0, "tokens_out": 0, "error": "no_key"}
        model_map = {"gemini_flash": "gemini-2.0-flash", "gemini_pro": "gemini-1.5-pro"}
        model_id = model_map.get(model, "gemini-2.0-flash")
        payload = json.dumps({
            "contents": [{"parts": [{"text": query}]}],
            "systemInstruction": {"parts": [{"text": system_prompt or "You are a helpful assistant."}]},
            "generationConfig": {"maxOutputTokens": max_tokens},
        }).encode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = ""
                for c in data.get("candidates", []):
                    for p in c.get("content", {}).get("parts", []):
                        text += p.get("text", "")
                return {"response": text, "model": model,
                        "tokens_in": len(query) // 4, "tokens_out": len(text) // 4}
        except Exception as e:
            return {"response": f"[Gemini error: {e}]", "model": model,
                    "tokens_in": 0, "tokens_out": 0, "error": str(e)}

    def _call_openai(self, model, query, system_prompt, max_tokens) -> dict:
        import urllib.request
        api_key = self.keys.get("OPENAI_API_KEY", "")
        if not api_key:
            return {"response": "[No OpenAI API key]", "model": model,
                    "tokens_in": 0, "tokens_out": 0, "error": "no_key"}
        model_map = {"gpt4o_mini": "gpt-4o-mini", "gpt4o": "gpt-4o", "gpt4": "gpt-4"}
        payload = json.dumps({
            "model": model_map.get(model, model), "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                {"role": "user", "content": query},
            ],
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions", data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return {"response": text, "model": model,
                        "tokens_in": usage.get("prompt_tokens", len(query) // 4),
                        "tokens_out": usage.get("completion_tokens", len(text) // 4)}
        except Exception as e:
            return {"response": f"[OpenAI error: {e}]", "model": model,
                    "tokens_in": 0, "tokens_out": 0, "error": str(e)}

    def _call_openrouter(self, query, system_prompt, max_tokens) -> dict:
        import urllib.request
        api_key = self.keys.get("OPENROUTER_API_KEY", "")
        if not api_key:
            return self._call_local(query, system_prompt, max_tokens)
        payload = json.dumps({
            "model": "meta-llama/llama-3.1-8b-instruct:free",
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                {"role": "user", "content": query},
            ],
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions", data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["choices"][0]["message"]["content"]
                return {"response": text, "model": "openrouter_free",
                        "tokens_in": len(query) // 4, "tokens_out": len(text) // 4}
        except Exception:
            return self._call_local(query, system_prompt, max_tokens)


# ═══════════════════════════════════════════════════════════
# MODEL SELECTION
# ═══════════════════════════════════════════════════════════

def select_model(tier: int, available_keys: set) -> str:
    candidates = TIER_MODELS.get(tier, TIER_MODELS[2])
    for model in candidates:
        p = PRICING.get(model, {})
        if p.get("tier", 99) <= 1:
            return model
        if model in ("haiku", "sonnet", "opus") and "ANTHROPIC_API_KEY" in available_keys:
            return model
        if model in ("gpt4o_mini", "gpt4o", "gpt4") and "OPENAI_API_KEY" in available_keys:
            return model
        if model in ("gemini_flash", "gemini_pro") and "GEMINI_API_KEY" in available_keys:
            return model
    if tier > 0:
        return select_model(tier - 1, available_keys)
    return "ollama_local"


# ═══════════════════════════════════════════════════════════
# KLAW ROUTER — THE PRODUCT
# ═══════════════════════════════════════════════════════════

class KlawRouter:
    """
    KLAW — K-104 Intelligent Model Router.

    Routes queries to the cheapest capable model. Tracks savings. Enforces spend limits.
    Paid tiers (2+) require an active KLAW license ($10/mo).

    Usage:
        router = KlawRouter(api_keys={"ANTHROPIC_API_KEY": "sk-..."})
        result = router.route("How do I center a div?")
        print(result["response"], result["cost"], result["savings"])
    """

    # Tiers 0-1 are free, tiers 2+ require a license
    FREE_TIER_CEILING = 1

    def __init__(self, api_keys: dict = None, daily_cap: float = 5.00,
                 monthly_budget: float = 50.00, max_tier: int = 3,
                 data_dir: Path = None, license_key: str = None,
                 skip_license: bool = False):
        self.classifier = KClassifier()
        self.cost = CostEngine(daily_cap=daily_cap, monthly_budget=monthly_budget,
                               data_dir=data_dir)
        self.backends = Backends(api_keys=api_keys)
        self.max_tier = max_tier
        self.available_keys = set(self.backends.keys.keys())
        self._license_key = license_key
        self._skip_license = skip_license
        self._license_status = None  # Lazy-checked

    @property
    def license(self):
        """Check license status (cached after first check)."""
        if self._skip_license:
            # Dev/internal mode — skip license checks
            from klaw.auth import LicenseStatus
            return LicenseStatus(valid=True, tier="pro", status="dev")
        if self._license_status is None:
            from klaw.auth import verify_license
            self._license_status = verify_license(self._license_key)
        return self._license_status

    @property
    def licensed(self) -> bool:
        return self.license.can_use_paid

    def route(self, query: str, system_prompt: str = "",
              max_tokens: int = 1024, force_tier: int = None) -> dict:
        start = time.time()

        # 1. Classify
        classification = self.classifier.classify(query)
        target_tier = force_tier if force_tier is not None else classification["tier"]
        target_tier = min(target_tier, self.max_tier)

        # 2. License gate — paid tiers require active subscription
        if target_tier > self.FREE_TIER_CEILING and not self.licensed:
            target_tier = self.FREE_TIER_CEILING
            classification["_license_downgrade"] = True
            classification["_license_error"] = self.license.error

        # 3. Budget check
        max_affordable = self.cost.max_affordable_tier()
        if target_tier > max_affordable:
            target_tier = max_affordable

        # 4. Template response
        if target_tier == 0 and classification.get("template_response"):
            resp = classification["template_response"]
            cr = self.cost.record("template", len(query), len(resp), 0)
            return {
                "response": resp,
                "tier": 0, "tier_name": "template",
                "model": "template", "model_label": "K-Template (FREE)",
                "cost": 0.0, "baseline_cost": cr["baseline_cost"],
                "savings": cr["savings"], "classification": classification,
                "latency_ms": int((time.time() - start) * 1000),
                "licensed": self.licensed,
            }

        # 5. Select model
        model = select_model(target_tier, self.available_keys)

        # 6. Pre-flight cost check
        est_cost = self.cost.estimate_cost(model, len(query), max_tokens * 4)
        can_afford, _ = self.cost.can_afford(est_cost)
        while not can_afford and target_tier > 0:
            target_tier -= 1
            model = select_model(target_tier, self.available_keys)
            est_cost = self.cost.estimate_cost(model, len(query), max_tokens * 4)
            can_afford, _ = self.cost.can_afford(est_cost)

        # 7. Call
        result = self.backends.call(model, query, system_prompt, max_tokens)
        response_text = result.get("response", "")

        # 8. Record
        actual_model = result.get("model", model)
        actual_tier = PRICING.get(actual_model, {}).get("tier", target_tier)
        cr = self.cost.record(
            actual_model,
            result.get("tokens_in", len(query) // 4) * 4,
            result.get("tokens_out", len(response_text) // 4) * 4,
            actual_tier,
        )

        resp = {
            "response": response_text,
            "tier": actual_tier,
            "tier_name": TIER_NAMES.get(actual_tier, "?"),
            "model": actual_model,
            "model_label": PRICING.get(actual_model, {}).get("label", actual_model),
            "cost": cr["actual_cost"],
            "baseline_cost": cr["baseline_cost"],
            "savings": cr["savings"],
            "daily_remaining": cr["daily_remaining"],
            "classification": classification,
            "latency_ms": int((time.time() - start) * 1000),
            "error": result.get("error"),
            "licensed": self.licensed,
        }

        # Add upgrade nudge if downgraded
        if classification.get("_license_downgrade"):
            resp["license_notice"] = (
                "Query was routed to free tier. "
                "Upgrade to KLAW Pro ($10/mo) for access to paid models. "
                "Run: klaw setup"
            )

        return resp

    def classify(self, query: str) -> dict:
        return self.classifier.classify(query)

    def stats(self) -> dict:
        stats = self.cost.get_stats()
        stats["licensed"] = self.licensed
        stats["license_status"] = self.license.status if self.license else "unknown"
        return stats
