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
import sys

from klaw.router import KlawRouter, TIER_NAMES


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
