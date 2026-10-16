"""Stock Lookup chat: Claude answers stock questions by calling the same five tools
the MCP server exposes (stock_server.TOOLS), using the Messages API tool-use loop.

Numbers always come from the tools; Claude only chooses the tool and words the answer.
"""
import json
import urllib.error
import urllib.request

from copilot import config
from copilot.llm import API_URL, LLMError, Usage, _headers
import stock_server

SYSTEM = (
    "You answer questions from sales and account managers about refurbished phone stock. "
    "Use the tools for every number: never estimate or invent stock, prices or dates. "
    "Grades run from A (best) to D. Sites: 'main warehouse' (WH1) and 'refurbishment hub' (WH2). "
    "When a site is asked for, pass it as the site filter and report units_here, not lot totals. "
    "Keep answers short: first the answer in one sentence, then a compact table or list with lot ids. "
    "Mention that the data is synthetic only if asked. If a question is outside stock, supply or data "
    "quality, say what the tools can answer instead."
)

TOOLS = [{"name": t["name"], "description": t["description"], "input_schema": t["inputSchema"]}
         for t in stock_server.tool_list()]


def _call(messages, usage, max_tokens=1200):
    payload = {"model": config.CLAUDE_MODEL, "max_tokens": max_tokens, "system": SYSTEM,
               "tools": TOOLS, "messages": messages}
    req = urllib.request.Request(API_URL, data=json.dumps(payload).encode(), method="POST", headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise LLMError(f"Claude API returned HTTP {e.code}: {msg or e.reason}") from None
    except urllib.error.URLError as e:
        raise LLMError(f"Could not reach the Claude API: {e.reason}") from None
    usage.add(data.get("usage", {}))
    return data


def run_tool(name, args):
    if name not in stock_server.TOOLS:
        return {"error": f"Unknown tool {name}"}
    try:
        return stock_server.TOOLS[name][0](**(args or {}))
    except Exception as e:
        return {"error": f"{e.__class__.__name__}: {e}"}


def ask(history, question, max_rounds=6):
    """history: list of Messages-API messages from earlier turns (mutated in place).
    Returns (answer_text, tool_calls, usage)."""
    usage = Usage()
    history.append({"role": "user", "content": question})
    calls = []
    for _ in range(max_rounds):
        data = _call(history, usage)
        content = data.get("content", [])
        history.append({"role": "assistant", "content": content})
        uses = [b for b in content if b.get("type") == "tool_use"]
        if not uses:
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
            return text, calls, usage
        results = []
        for u in uses:
            out = run_tool(u["name"], u.get("input"))
            calls.append({"tool": u["name"], "input": u.get("input"), "output": out})
            results.append({"type": "tool_result", "tool_use_id": u["id"],
                            "content": json.dumps(out, ensure_ascii=False), "is_error": "error" in out})
        history.append({"role": "user", "content": results})
    return "I needed more lookups than allowed for one question. Try a narrower question.", calls, usage
