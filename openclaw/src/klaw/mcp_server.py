"""
KLAW MCP Server — Expose K-104 routing as MCP tools for Claude Code.

Tools:
    klaw_route: Route a query through K-104 to the cheapest capable model
    klaw_classify: Classify a query without calling any model
    klaw_stats: Get usage and savings statistics

Install in Claude Code:
    Add to .mcp.json:
    {
        "mcpServers": {
            "klaw": {
                "command": "python",
                "args": ["-m", "klaw", "mcp"]
            }
        }
    }

    Or if installed via pip:
    {
        "mcpServers": {
            "klaw": {
                "command": "klaw",
                "args": ["mcp"]
            }
        }
    }
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from html.parser import HTMLParser

from klaw.router import KlawRouter, TIER_NAMES

ROOT = Path(os.environ.get("KLAW_ROOT", Path.home() / ".klaw"))
CONFIG_PATH = ROOT / "config" / "bridge_config.json"


def _load_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ── Safety gate ─────────────────────────────────────────────────────────────

_BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/", r"format\s+[A-Z]:", r"del\s+/[sS]", r"shutdown",
    r"mkfs", r"dd\s+if=", r":(){ :|:& };:", r">\s*/dev/sd",
]

def _is_safe_command(cmd: str) -> tuple:
    """Check command against OathGuard safety patterns. Returns (safe, reason)."""
    for pat in _BLOCKED_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return False, f"Blocked by OathGuard: matches pattern '{pat}'"
    config = _load_config()
    extra_blocked = config.get("exec_blocked_patterns", [])
    for pat in extra_blocked:
        if pat.lower() in cmd.lower():
            return False, f"Blocked by config: '{pat}'"
    return True, "OK"


# ── HTML stripper ───────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self._skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = True
    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = False
    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)
    def get_text(self):
        return " ".join(self.text)


_router = None

def _get_router():
    global _router
    if _router is None:
        _router = KlawRouter()
    return _router


def handle_route(params):
    """Route a query through KLAW."""
    query = params.get("query", "")
    if not query:
        return {"error": "query parameter required"}

    router = _get_router()
    result = router.route(
        query,
        system_prompt=params.get("system_prompt", ""),
        max_tokens=params.get("max_tokens", 1024),
        force_tier=params.get("tier"),
    )

    return {
        "response": result["response"],
        "tier": result["tier_name"],
        "model": result["model_label"],
        "cost": f"${result['cost']:.6f}",
        "savings": f"${result['savings']:.6f}",
        "latency_ms": result.get("latency_ms", 0),
        "suit": result["classification"]["suit"],
        "k_address": result["classification"]["k_address"],
    }


def handle_classify(params):
    """Classify a query without calling any model."""
    query = params.get("query", "")
    if not query:
        return {"error": "query parameter required"}

    router = _get_router()
    c = router.classify(query)
    return {
        "tier": c["tier"],
        "tier_name": TIER_NAMES.get(c["tier"], "?"),
        "suit": c["suit"],
        "polarity": c["polarity"],
        "confidence": c["confidence"],
        "reason": c["reason"],
        "k_address": c["k_address"],
        "has_template": c.get("template_response") is not None,
    }


def handle_stats(params):
    """Get usage and savings statistics."""
    router = _get_router()
    stats = router.stats()
    return {
        "total_queries": stats["total_queries"],
        "total_cost": f"${stats['total_cost']:.4f}",
        "total_savings": f"${stats['total_savings']:.4f}",
        "savings_ratio": f"{stats['savings_ratio']*100:.1f}%",
        "avg_cost_per_query": f"${stats['avg_cost_per_query']:.6f}",
        "today_cost": f"${stats['daily_cost']:.4f}",
        "today_queries": stats["daily_queries"],
        "tier_distribution": stats.get("tier_percentages", {}),
    }


# ── New hub tool handlers ───────────────────────────────────────────────────

def handle_exec(params):
    """K-classified shell execution with OathGuard safety gate."""
    cmd = params.get("command", "")
    if not cmd:
        return {"error": "command parameter required"}
    confirm = params.get("confirm", False)

    # Safety gate
    safe, reason = _is_safe_command(cmd)
    if not safe:
        if not confirm:
            return {"blocked": True, "reason": reason,
                    "hint": "Set confirm: true to override (use with caution)"}
        # Even with confirm, absolute blocks stay
        if "OathGuard" in reason:
            return {"blocked": True, "reason": reason, "override": False}

    # Classify the command itself
    router = _get_router()
    c = router.classify(cmd)

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30,
            cwd=str(ROOT),
        )
        output = result.stdout[:4000] if result.stdout else ""
        stderr = result.stderr[:1000] if result.stderr else ""
        return {
            "output": output,
            "stderr": stderr,
            "returncode": result.returncode,
            "k_address": c["k_address"],
            "suit": c["suit"],
        }
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out (30s limit)"}
    except Exception as e:
        return {"error": str(e)}


def handle_browse(params):
    """Fetch a URL, strip HTML, K-classify the content."""
    url = params.get("url", "")
    if not url:
        return {"error": "url parameter required"}
    max_chars = params.get("max_chars", 3000)

    try:
        req = Request(url, headers={"User-Agent": "KLAW/0.2 (+kit.triv)"})
        with urlopen(req, timeout=15) as resp:
            raw_html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return {"error": f"Fetch failed: {e}"}

    # Strip HTML to text
    stripper = _HTMLStripper()
    stripper.feed(raw_html)
    text = stripper.get_text()
    text = re.sub(r'\s+', ' ', text).strip()[:max_chars]

    # K-classify the content
    router = _get_router()
    c = router.classify(text[:500])

    # Extract title
    title_match = re.search(r"<title>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else url

    return {
        "title": title,
        "text": text,
        "k_address": c["k_address"],
        "suit": c["suit"],
        "polarity": c["polarity"],
        "url": url,
        "chars": len(text),
    }


def handle_file(params):
    """Read, write, or search files with K-tagging."""
    action = params.get("action", "read")
    path_str = params.get("path", "")

    if action == "search":
        query = params.get("query", "")
        if not query:
            return {"error": "query parameter required for search"}
        # Simple filename + content grep
        matches = []
        search_root = ROOT
        for p in search_root.rglob("*"):
            if p.is_file() and p.suffix in (".py", ".js", ".ts", ".md", ".json", ".svelte"):
                if query.lower() in p.name.lower():
                    matches.append(str(p.relative_to(ROOT)))
                elif p.stat().st_size < 100000:
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        if query.lower() in content.lower():
                            matches.append(str(p.relative_to(ROOT)))
                    except Exception:
                        pass
            if len(matches) >= 20:
                break
        return {"matches": matches, "count": len(matches)}

    if not path_str:
        return {"error": "path parameter required"}
    path = Path(path_str) if Path(path_str).is_absolute() else ROOT / path_str

    if action == "read":
        if not path.exists():
            return {"error": f"File not found: {path}"}
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            # K-classify if small enough
            router = _get_router()
            c = router.classify(content[:500])
            return {
                "content": content[:10000],
                "path": str(path),
                "size": path.stat().st_size,
                "k_address": c["k_address"],
                "suit": c["suit"],
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "write":
        content = params.get("content", "")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"written": str(path), "bytes": len(content.encode("utf-8"))}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown action: {action}. Use read/write/search."}


def handle_fleet(params):
    """Send command to a mesh peer or check fleet status."""
    action = params.get("action", "status")

    if action == "status":
        # Check mesh state
        config = _load_config()
        mesh_port = config.get("mesh_port", 7104)
        import socket
        peers = []
        # Try to read mesh state file
        mesh_state = ROOT / "cell" / ".mesh_state.json"
        if mesh_state.exists():
            try:
                state = json.loads(mesh_state.read_text(encoding="utf-8"))
                peers = state.get("peers", [])
            except Exception:
                pass
        return {
            "mesh_port": mesh_port,
            "mesh_role": config.get("mesh_role", "unknown"),
            "peers": peers,
            "machine": __import__("socket").gethostname(),
        }

    elif action == "send":
        target = params.get("target", "")
        message = params.get("message", "")
        if not target or not message:
            return {"error": "target and message required for send action"}
        # Import mesh client
        try:
            sys.path.insert(0, str(ROOT))
            from cell.mesh import MeshClient
            client = MeshClient(target)
            client.send_bus_message("nucleus", {
                "type": "fleet_command",
                "body": message,
                "from": __import__("socket").gethostname(),
            })
            return {"sent": True, "target": target, "message": message[:200]}
        except Exception as e:
            return {"error": f"Fleet send failed: {e}"}

    return {"error": f"Unknown action: {action}. Use status/send."}


def handle_timeline(params):
    """Run a KFlash quaternary timeline — fire K-addressed agent frames in sequence."""
    code = params.get("code", "")
    if not code:
        return {"error": "code parameter required — e.g. '0123' or 'HSDC'"}

    scripts = params.get("scripts", [])
    rank = params.get("rank", 7)
    polarity = params.get("polarity", "+")
    preset = params.get("preset", "")

    try:
        sys.path.insert(0, str(ROOT / "k_swarm"))
        from k_flash import KFlash, PRESETS, encode, decode, to_int
    except ImportError as e:
        return {"error": f"KFlash not found: {e}. Check k_swarm/k_flash.py"}

    flash = KFlash(verbose=False)

    try:
        if preset:
            if preset not in PRESETS:
                return {"error": f"Unknown preset '{preset}'. Available: {list(PRESETS.keys())}"}
            result = flash.play_preset(preset, scripts=scripts or None, rank=rank, polarity=polarity)
        else:
            result = flash.play(code, scripts=scripts or None, rank=rank, polarity=polarity)
    except Exception as e:
        return {"error": str(e)}

    return {
        "code": result.code,
        "pipeline_id": result.pipeline_id,
        "suits": decode(result.code),
        "frames": [
            {
                "index": r.frame.index,
                "k_addr": r.frame.k_addr,
                "role": r.frame.role,
                "script": r.frame.script,
                "response": r.response,
                "tier": r.tier,
                "cost": f"${r.cost:.6f}",
                "latency_ms": round(r.latency_ms),
                "success": r.success,
                "error": r.error if not r.success else "",
            }
            for r in result.frames
        ],
        "total_cost": f"${result.total_cost:.6f}",
        "total_latency_ms": round(result.total_latency_ms),
        "success": result.success,
    }


def handle_push(params):
    """Push notification to phone via ntfy."""
    title = params.get("title", "KLAW")
    body = params.get("body", "")
    if not body:
        return {"error": "body parameter required"}
    priority = params.get("priority", "default")

    # Map K-rank to ntfy priority if rank provided
    rank = params.get("rank")
    if rank is not None:
        rank = int(rank)
        if rank >= 12:
            priority = "urgent"
        elif rank >= 9:
            priority = "high"
        elif rank >= 5:
            priority = "default"
        else:
            priority = "low"

    try:
        sys.path.insert(0, str(ROOT))
        from cell.phone_notifier import notify_phone
        result = notify_phone(title, body, priority=priority)
        return {"sent": result, "title": title, "priority": priority}
    except Exception as e:
        return {"error": f"Push failed: {e}"}


TOOLS = {
    "klaw_route": {
        "handler": handle_route,
        "description": "Route a query through KLAW K-104 intelligent model router. Automatically selects the cheapest model that can handle the query. Returns the response, cost, and savings vs baseline.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The query to route"},
                "system_prompt": {"type": "string", "description": "Optional system prompt"},
                "max_tokens": {"type": "integer", "description": "Max output tokens (default 1024)", "default": 1024},
                "tier": {"type": "integer", "description": "Force a specific tier (0-4). Omit for auto-routing.", "minimum": 0, "maximum": 4},
            },
            "required": ["query"],
        },
    },
    "klaw_classify": {
        "handler": handle_classify,
        "description": "Classify a query's semantic domain and complexity without calling any model. Returns suit (hearts/spades/diamonds/clubs), tier, polarity, and K-address.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The query to classify"},
            },
            "required": ["query"],
        },
    },
    "klaw_stats": {
        "handler": handle_stats,
        "description": "Get KLAW usage statistics including total queries, cost, savings, and tier distribution.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    "klaw_exec": {
        "handler": handle_exec,
        "description": "K-classified shell execution with OathGuard safety gate. Classifies command, checks safety, executes, K-tags result.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "confirm": {"type": "boolean", "description": "Set true to override soft blocks (OathGuard hard blocks cannot be overridden)", "default": False},
            },
            "required": ["command"],
        },
    },
    "klaw_browse": {
        "handler": handle_browse,
        "description": "Fetch a URL, strip HTML to text, K-classify the content. Returns title, text, and K-address.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "max_chars": {"type": "integer", "description": "Max chars of text to return (default 3000)", "default": 3000},
            },
            "required": ["url"],
        },
    },
    "klaw_file": {
        "handler": handle_file,
        "description": "Read, write, or search files with K-tagging. Actions: read (default), write, search.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "read, write, or search", "default": "read"},
                "path": {"type": "string", "description": "File path (relative to kit.triv or absolute)"},
                "content": {"type": "string", "description": "Content to write (for write action)"},
                "query": {"type": "string", "description": "Search query (for search action)"},
            },
        },
    },
    "klaw_fleet": {
        "handler": handle_fleet,
        "description": "Fleet mesh management. Check connected peers or send commands to mesh machines.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "status or send", "default": "status"},
                "target": {"type": "string", "description": "Target machine hostname/IP (for send)"},
                "message": {"type": "string", "description": "Message to send (for send)"},
            },
        },
    },
    "klaw_timeline": {
        "handler": handle_timeline,
        "description": "Run a KFlash quaternary timeline — fire K-addressed agent frames in sequence. Suits map to base-4: H=0 S=1 D=2 C=3. Pipeline '0123' (id=27) = H→S→D→C full run. Returns per-frame responses, costs, and K-addresses.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Quaternary code e.g. '0123' or suit string 'HSDC'. Ignored if preset is set."},
                "scripts": {"type": "array", "items": {"type": "string"}, "description": "Script/prompt per frame. Fewer scripts than frames is OK — extras run empty."},
                "preset": {"type": "string", "description": "Named preset: full_run, build_sprint, exec_sprint, warmup, research, ship_it, stc_build, affiliate"},
                "rank": {"type": "integer", "description": "K-rank for all frames (1-13, default 7)", "default": 7, "minimum": 1, "maximum": 13},
                "polarity": {"type": "string", "description": "Polarity for all frames: '+' or '-' (default '+')", "default": "+"},
            },
        },
    },
    "klaw_push": {
        "handler": handle_push,
        "description": "Push notification to Kit's phone via ntfy. Optionally map K-rank to priority.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Notification title", "default": "KLAW"},
                "body": {"type": "string", "description": "Notification body text"},
                "priority": {"type": "string", "description": "min/low/default/high/urgent", "default": "default"},
                "rank": {"type": "integer", "description": "K-rank (1-13) to auto-map to priority"},
            },
            "required": ["body"],
        },
    },
}


def handle_request(request):
    """Handle a single MCP JSON-RPC request."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "klaw",
                    "version": "0.1.0",
                    "description": "KLAW Router -- K-104 Intelligent Model Router",
                },
            },
        }

    elif method == "notifications/initialized":
        return None

    elif method == "tools/list":
        tool_list = []
        for name, tool in TOOLS.items():
            tool_list.append({
                "name": name,
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
            })
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tool_list},
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        tool = TOOLS.get(tool_name)
        if not tool:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"error": f"unknown tool: {tool_name}"})}],
                    "isError": True,
                },
            }
        try:
            result = tool["handler"](tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}],
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                    "isError": True,
                },
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


def main():
    """Run the MCP server on stdio."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
