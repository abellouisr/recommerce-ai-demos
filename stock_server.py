"""Recommerce Stock Lookup – an MCP server (stdio, Python standard library only).

Lets Claude (Desktop or any MCP client) answer questions such as
  "How many grade A iPhone 13 128GB, unlocked, do we have in the main warehouse?"
  "What iPhone 14 supply is arriving in the next two weeks?"
  "What is wrong with the raw stock export?"
against a cleaned version of a messy reseller-portal export.

All data is synthetic. Run `python selftest.py` to check it works.
"""
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works from any folder

from stock.catalogue import TODAY, inbound_shipments, raw_rows
from stock.clean import clean

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "recommerce-stock", "version": "1.0.0"}
GRADE_ORDER = "ABCD"
SITE = {"WH1": "Main warehouse", "WH2": "Refurbishment hub"}

LOTS, QUALITY = clean(raw_rows())
LOT_BY_ID = {l["lot_id"]: l for l in LOTS}
INBOUND = inbound_shipments()


# ---------------------------------------------------------------- tools
def _match(text, lot):
    words = text.lower().replace("gb", " gb").split()
    hay = f"{lot['brand']} {lot['model']} {lot['storage_gb']} gb {lot['colour']}".lower()
    return all(w in hay for w in words)


def _site_match(site, loc):
    return site.lower() in f"{loc} {SITE[loc[:3]]}".lower()


def search_stock(query="", min_grade="D", min_quantity=1, unlocked_only=False,
                 site="", max_unit_price_eur=None, limit=15):
    worst = GRADE_ORDER.index(min_grade.upper()) if min_grade else 3
    hits = []
    for lot in LOTS:
        if query and not _match(query, lot):
            continue
        if GRADE_ORDER.index(lot["grade"]) > worst:
            continue
        if unlocked_only and lot["lock"] != "unlocked":
            continue
        if max_unit_price_eur and lot["avg_unit_price_eur"] > max_unit_price_eur:
            continue
        # Count only the units physically at the requested site (a lot can be split across sites)
        if site:
            units = sum(q for loc, q in lot["units_by_location"].items() if _site_match(site, loc))
            where = [loc for loc in lot["units_by_location"] if _site_match(site, loc)]
        else:
            units, where = lot["quantity"], lot["locations"]
        if units < max(min_quantity or 1, 1):
            continue
        hits.append((lot, units, where))
    hits.sort(key=lambda h: (GRADE_ORDER.index(h[0]["grade"]), -h[1]))
    return {
        "site_filter": site or "all sites",
        "matching_lots": len(hits),
        "total_units": sum(u for _, u, _ in hits),
        "by_grade": {g: sum(u for l, u, _ in hits if l["grade"] == g) for g in "ABCD"},
        "lots": [{"lot_id": l["lot_id"], "units_here": u, "lot_total_units": l["quantity"],
                  "locations_here": w, "summary": l["summary"]} for l, u, w in hits[:limit]],
        "note": "units_here counts only units at the requested site. Rows with no grade or a price typo "
                "are held back (see data_quality_report).",
    }


def lot_details(lot_id):
    lot = LOT_BY_ID.get(lot_id.upper().strip())
    if not lot:
        return {"error": f"No lot {lot_id}. Use search_stock to find lot ids."}
    return lot


def incoming_supply(query="", days_ahead=30):
    until = TODAY + timedelta(days=days_ahead)
    rows = [s for s in INBOUND if date.fromisoformat(s["eta"]) <= until
            and (not query or all(w in f"{s['brand']} {s['model']} {s['storage_gb']} gb".lower()
                                  for w in query.lower().replace("gb", " gb").split()))]
    rows.sort(key=lambda s: s["eta"])
    expected = defaultdict(float)
    for s in rows:
        for g, share in s["expected_grade_mix"].items():
            expected[g] += s["units"] * share
    return {
        "as_of": str(TODAY),
        "window": f"next {days_ahead} days (until {until})",
        "shipments": len(rows),
        "units_expected": sum(s["units"] for s in rows),
        "expected_by_grade": {g: round(v) for g, v in sorted(expected.items())},
        "detail": rows,
        "note": "Grade mix is a forecast from each partner's history; final grades are set at goods-in.",
    }


def data_quality_report():
    q = dict(QUALITY)
    q["held_back"] = q["held_back"][:15] + ([{"more": len(QUALITY["held_back"]) - 15}] if len(QUALITY["held_back"]) > 15 else [])
    q["what_this_means"] = [
        f"{q['raw_rows']} raw rows became {q['lots_after_merge']} clean lots.",
        f"{q['rows_held_back']} rows cannot be sold as listed until someone fixes them.",
        f"{q['rows_without_photo']} rows have no photo and {q['rows_without_battery_reading']} have no battery reading – buyers ask for both.",
        f"{q['locked_units']} units are still iCloud/MDM locked and should not be offered as unlocked.",
    ]
    return q


def stock_overview(group_by="model"):
    key = {"model": lambda l: f"{l['brand']} {l['model']}", "brand": lambda l: l["brand"],
           "grade": lambda l: l["grade"]}.get(group_by)
    if group_by not in ("model", "brand", "grade", "site"):
        return {"error": "group_by must be model, brand, grade or site"}
    units, value = Counter(), Counter()
    for l in LOTS:
        for loc, q in l["units_by_location"].items():  # split by where units physically are
            k = SITE[loc[:3]] if group_by == "site" else key(l)
            units[k] += q
            value[k] += q * l["avg_unit_price_eur"]
    return {
        "group_by": group_by,
        "total_units": sum(units.values()),
        "total_value_eur": round(sum(value.values())),
        "rows": [{"group": k, "units": u, "value_eur": round(value[k])} for k, u in units.most_common()],
    }


TOOLS = {
    "search_stock": (search_stock, "Find sellable device lots. Free-text model search (e.g. 'iPhone 13 128GB'), "
                     "minimum grade (A best, D worst), unlocked only, site (main warehouse, refurbishment hub, WH1, WH2 or a location code) and max price.", {
        "query": {"type": "string", "description": "Model text, e.g. 'iPhone 13 128GB' or 'Galaxy S22 black'"},
        "min_grade": {"type": "string", "enum": ["A", "B", "C", "D"], "description": "Worst acceptable grade"},
        "min_quantity": {"type": "integer", "description": "Only lots with at least this many units"},
        "unlocked_only": {"type": "boolean"},
        "site": {"type": "string", "description": "'main', 'refurbishment', WH1, WH2 or a location code like WH1-A2"},
        "max_unit_price_eur": {"type": "number"},
        "limit": {"type": "integer", "default": 15},
    }, []),
    "lot_details": (lot_details, "Everything about one lot: battery range, box, locations, photo coverage, source rows.", {
        "lot_id": {"type": "string", "description": "e.g. L-0042"},
    }, ["lot_id"]),
    "incoming_supply": (incoming_supply, "Trade-in shipments on their way from partners, with ETA and expected grade mix.", {
        "query": {"type": "string", "description": "Model text, e.g. 'iPhone 14'"},
        "days_ahead": {"type": "integer", "default": 30},
    }, []),
    "data_quality_report": (data_quality_report, "What was wrong with the raw export, what was fixed, and which rows are held back.", {}, []),
    "stock_overview": (stock_overview, "Units and value of sellable stock grouped by model, brand, grade or site.", {
        "group_by": {"type": "string", "enum": ["model", "brand", "grade", "site"], "default": "model"},
    }, []),
}


def tool_list():
    return [{"name": n, "description": d,
             "inputSchema": {"type": "object", "properties": props, "required": req}}
            for n, (_, d, props, req) in TOOLS.items()]


# ---------------------------------------------------------------- MCP protocol (JSON-RPC 2.0 over stdio)
def handle(msg):
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:  # notification, e.g. notifications/initialized
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
                  "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO,
                  "instructions": "Stock lookup for refurbished phones. Grades: A best, D worst. "
                                  "Use search_stock first, then lot_details for a specific lot."}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": tool_list()}
    elif method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Unknown tool {name}"}}
        try:
            out = TOOLS[name][0](**args)
            result = {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False, indent=1)}],
                      "isError": "error" in out}
        except Exception as e:  # report to the model instead of crashing
            result = {"content": [{"type": "text", "text": f"Tool error: {e}"}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"recommerce-stock MCP server ready: {len(LOTS)} lots, {len(INBOUND)} inbound shipments", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            reply = handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
