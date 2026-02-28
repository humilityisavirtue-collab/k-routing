"""
OpenPod Models -- One-command local model setup.

Wraps Ollama + PyTorch into zero-friction model management.
Detect, pull, test, route. No config files. No YAML. Just works.

Usage:
    from openpod.models import LocalModels
    lm = LocalModels()
    lm.setup()                     # Pull recommended models
    lm.ask("hermes3:8b", "hello")  # Generate
    lm.embed("hermes3:8b", "text") # Embed
    lm.status()                    # What's running
"""

import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict


OLLAMA_BASE = "http://localhost:11434"

# Recommended models by role
RECOMMENDED = {
    "router": {
        "model": "hermes3:8b",
        "size": "4.7GB",
        "purpose": "K-suit routing + generation",
        "required": True,
    },
    "fast": {
        "model": "tinyllama:latest",
        "size": "637MB",
        "purpose": "K-lens classifier, pulse, quick routing",
        "required": False,
    },
    "reason": {
        "model": "gemma3:4b",
        "size": "3.3GB",
        "purpose": "Local generation fallback",
        "required": False,
    },
}


@dataclass
class ModelStatus:
    name: str
    available: bool
    size: str = ""
    modified: str = ""
    error: str = ""


class LocalModels:
    """
    Zero-friction local model management via Ollama.

    Detects Ollama, pulls models, tests inference, reports status.
    No config files. No YAML. Just works.
    """

    def __init__(self, base_url: str = OLLAMA_BASE):
        self.base_url = base_url.rstrip("/")

    # ── Detection ─────────────────────────────────────────────

    def ollama_running(self) -> bool:
        """Check if Ollama is running."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            return False

    def ollama_installed(self) -> bool:
        """Check if Ollama CLI is installed."""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def list_models(self) -> List[ModelStatus]:
        """List locally available models."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = []
                for m in data.get("models", []):
                    name = m.get("name", "")
                    size_bytes = m.get("size", 0)
                    size_gb = f"{size_bytes / 1e9:.1f}GB" if size_bytes else ""
                    models.append(ModelStatus(
                        name=name,
                        available=True,
                        size=size_gb,
                        modified=m.get("modified_at", ""),
                    ))
                return models
        except Exception as e:
            return [ModelStatus(name="(error)", available=False, error=str(e))]

    def has_model(self, model: str) -> bool:
        """Check if a specific model is available locally."""
        models = self.list_models()
        return any(m.name.startswith(model.split(":")[0]) for m in models if m.available)

    # ── Pull ──────────────────────────────────────────────────

    def pull(self, model: str, stream_progress: bool = True) -> bool:
        """
        Pull a model via Ollama. Shows progress if stream_progress=True.
        Returns True on success.
        """
        if not self.ollama_running():
            print("  Ollama not running. Start with: ollama serve")
            return False

        print(f"  Pulling {model}...")
        try:
            payload = json.dumps({"name": model, "stream": stream_progress}).encode()
            req = urllib.request.Request(
                f"{self.base_url}/api/pull",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                if stream_progress:
                    last_status = ""
                    for line in resp:
                        try:
                            chunk = json.loads(line.decode("utf-8"))
                            status = chunk.get("status", "")
                            if status != last_status:
                                print(f"    {status}")
                                last_status = status
                        except json.JSONDecodeError:
                            pass
                else:
                    resp.read()
            print(f"  Done: {model}")
            return True
        except Exception as e:
            print(f"  Error pulling {model}: {e}")
            return False

    # ── Generate ──────────────────────────────────────────────

    def ask(
        self,
        model: str,
        prompt: str,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate text from a local model. Returns response string.
        """
        payload = json.dumps({
            "model": model,
            "messages": [
                *([{"role": "system", "content": system}] if system else []),
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("message", {}).get("content", "")
        except Exception as e:
            return f"[Error: {e}]"

    def embed(self, model: str, text: str) -> Optional[List[float]]:
        """Get embedding vector from a local model."""
        payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("embedding")
        except Exception:
            return None

    # ── Test ──────────────────────────────────────────────────

    def test(self, model: str) -> dict:
        """
        Quick inference test. Returns timing and response.
        """
        start = time.time()
        response = self.ask(model, "Say 'hello' and nothing else.", max_tokens=10, temperature=0)
        elapsed = time.time() - start

        return {
            "model": model,
            "response": response.strip()[:50],
            "latency_ms": int(elapsed * 1000),
            "ok": bool(response and not response.startswith("[Error")),
        }

    # ── Setup ─────────────────────────────────────────────────

    def setup(self, include_optional: bool = False) -> dict:
        """
        One-command local model setup.

        1. Check Ollama is running
        2. Pull recommended models
        3. Test each one
        4. Report status

        Returns dict with results.
        """
        results = {"ollama": False, "models": {}}

        # Step 1: Ollama check
        if not self.ollama_running():
            if self.ollama_installed():
                print("  Ollama installed but not running.")
                print("  Start it with: ollama serve")
            else:
                print("  Ollama not found.")
                print("  Install from: https://ollama.ai")
                print("  Then run: ollama serve")
            return results

        results["ollama"] = True
        print("  Ollama: running")

        # Step 2: Pull models
        for role, spec in RECOMMENDED.items():
            if not spec["required"] and not include_optional:
                continue

            model = spec["model"]
            if self.has_model(model):
                print(f"  {model}: already available ({spec['purpose']})")
            else:
                print(f"  {model}: pulling ({spec['size']}, {spec['purpose']})...")
                self.pull(model, stream_progress=True)

        # Step 3: Test
        print("\n  Testing models...")
        for role, spec in RECOMMENDED.items():
            if not spec["required"] and not include_optional:
                continue
            model = spec["model"]
            if self.has_model(model):
                t = self.test(model)
                status = "OK" if t["ok"] else "FAIL"
                print(f"    {model}: {status} ({t['latency_ms']}ms)")
                results["models"][model] = t
            else:
                print(f"    {model}: not available")
                results["models"][model] = {"ok": False, "error": "not_pulled"}

        return results

    def status(self) -> dict:
        """Full status report: Ollama + models + recommendations."""
        running = self.ollama_running()
        models = self.list_models() if running else []
        available_names = {m.name.split(":")[0] for m in models if m.available}

        missing = []
        for role, spec in RECOMMENDED.items():
            model_base = spec["model"].split(":")[0]
            if model_base not in available_names:
                missing.append(spec)

        return {
            "ollama_running": running,
            "ollama_installed": self.ollama_installed() if not running else True,
            "models_available": [
                {"name": m.name, "size": m.size}
                for m in models if m.available
            ],
            "models_missing": missing,
            "ready": running and not any(
                s["required"] for s in missing
            ),
        }


# ================================================================
# PyTorch helpers (optional, for weight-level work)
# ================================================================

def load_torch_model(model_name: str, device: str = "auto", dtype: str = "float16"):
    """
    Load a HuggingFace model with PyTorch. Auto-detects GPU.

    Usage:
        model, tokenizer = load_torch_model("TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    """
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
    except ImportError:
        raise ImportError(
            "PyTorch + transformers required.\n"
            "Install: pip install torch transformers"
        )

    dtype_map = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }
    torch_dtype = dtype_map.get(dtype, torch.float16)

    print(f"  Loading {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch_dtype,
        device_map=device,
    )
    model.eval()

    device_name = next(model.parameters()).device
    print(f"  Loaded on {device_name} ({dtype})")
    return model, tokenizer


def torch_available() -> dict:
    """Check PyTorch/CUDA availability."""
    result = {"torch": False, "cuda": False, "gpu_name": "", "vram_gb": 0}
    try:
        import torch
        result["torch"] = True
        result["cuda"] = torch.cuda.is_available()
        if result["cuda"]:
            result["gpu_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            vram = getattr(props, "total_memory", None) or getattr(props, "total_mem", 0)
            result["vram_gb"] = round(vram / 1e9, 1)
    except ImportError:
        pass
    return result
