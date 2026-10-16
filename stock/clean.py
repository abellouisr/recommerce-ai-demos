"""Turn the messy raw export into clean, sellable lots.

Steps: unify brand, model, storage and colour; map every grade label to one
A–D scale; merge duplicate rows into lots with a quantity; hold back rows that
cannot be sold as listed (no grade, price typo); write a one-line summary per lot;
and keep a report of everything that was changed.
"""
import re
from collections import Counter, defaultdict
from statistics import median

from .catalogue import BRAND_VARIANTS, COLOURS, MODELS, RAW_GRADES

_BRAND = {v.lower(): k for k, vs in BRAND_VARIANTS.items() for v in vs}
_COLOUR = {v.lower(): k for k, vs in COLOURS.items() for v in vs}
_MODELS = sorted({(b, m) for b, m, _, _ in MODELS}, key=lambda x: -len(x[1]))  # longest name first
_LOCK = {"cloudoff": "unlocked", "cloud locked": "iCloud locked", "mdm lock": "MDM locked", "": "lock not checked"}
STORAGE_RE = re.compile(r"(\d{2,4})\s*gb", re.I)


def _model(name):
    low = name.lower()
    for brand, model in _MODELS:
        if model.lower() in low:
            return brand, model
    return None, name


def clean(rows):
    report = Counter()
    variants = defaultdict(set)
    fixed, held = [], []

    for r in rows:
        brand_raw = r["manufacturer"]
        brand = _BRAND.get(brand_raw.lower(), brand_raw)
        name_brand, model = _model(r["product_name"])
        brand = name_brand or brand
        if brand_raw != brand:
            report["brand spelling unified"] += 1
            variants["brand"].add(f"{brand_raw} → {brand}")
        m = STORAGE_RE.search(r["product_name"])
        storage = int(m.group(1)) if m else None
        if m and m.group(0) != f"{storage}GB":
            report["storage format unified"] += 1
        colour = _COLOUR.get(r["colour"].lower(), r["colour"])
        if colour != r["colour"]:
            report["colour name unified"] += 1
            variants["colour"].add(f"{r['colour']} → {colour}")
        grade = RAW_GRADES.get(r["appearance"])
        if r["appearance"] not in ("A", "B", "C"):
            report["grade label mapped to A–D scale"] += 1
            variants["grade"].add(f"{r['appearance']} → {grade or 'needs regrade'}")
        lock = _LOCK.get(r["cloud_lock"].lower(), r["cloud_lock"])

        item = {**r, "brand": brand, "model": model, "storage_gb": storage, "colour_clean": colour,
                "grade": grade, "lock": lock}
        if grade is None:
            item["hold_reason"] = f"no usable grade ('{r['appearance']}') – send for regrade"
            held.append(item)
            continue
        fixed.append(item)

    # Price outliers: compare with the median for the same model / storage / grade
    groups = defaultdict(list)
    for it in fixed:
        groups[(it["model"], it["storage_gb"], it["grade"])].append(it["unit_price_eur"])
    sellable = []
    for it in fixed:
        med = median(groups[(it["model"], it["storage_gb"], it["grade"])])
        if med and (it["unit_price_eur"] > med * 3 or it["unit_price_eur"] < med * 0.3):
            it["hold_reason"] = f"price €{it['unit_price_eur']} vs typical €{med:.0f} – likely typo"
            held.append(it)
            report["price typo held back"] += 1
        else:
            sellable.append(it)

    # Merge duplicate rows into lots
    lots_map = defaultdict(list)
    for it in sellable:
        key = (it["brand"], it["model"], it["storage_gb"], it["grade"], it["colour_clean"], it["lock"], it["functionality"])
        lots_map[key].append(it)
    lots = []
    for n, (key, items) in enumerate(sorted(lots_map.items(), key=lambda kv: [str(x) for x in kv[0]]), start=1):
        brand, model, storage, grade, colour, lock, func = key
        qty = sum(i["quantity"] for i in items)
        avg_price = sum(i["unit_price_eur"] * i["quantity"] for i in items) / qty
        batteries = [i["battery_health"] for i in items if i["battery_health"]]
        boxes = Counter(i["boxed"] for i in items)
        photo_rows = sum(i["has_photo"] for i in items)
        lot = {
            "lot_id": f"L-{n:04d}",
            "brand": brand, "model": model, "storage_gb": storage, "grade": grade,
            "colour": colour, "lock": lock, "functionality": func,
            "quantity": qty,
            "avg_unit_price_eur": round(avg_price, 2),
            "min_unit_price_eur": min(i["unit_price_eur"] for i in items),
            "battery_min": min(batteries) if batteries else None,
            "battery_max": max(batteries) if batteries else None,
            "box": ", ".join(f"{k} ×{v}" for k, v in boxes.most_common()),
            "locations": sorted({i["location"] for i in items}),
            "units_by_location": {loc: sum(i["quantity"] for i in items if i["location"] == loc)
                                  for loc in sorted({i["location"] for i in items})},
            "source_rows": [i["row_id"] for i in items],
            "photo_coverage": round(photo_rows / len(items), 2),
        }
        lot["summary"] = summary(lot)
        lots.append(lot)
    report["duplicate rows merged into lots"] = len(sellable) - len(lots)

    quality = {
        "raw_rows": len(rows),
        "sellable_rows": len(sellable),
        "lots_after_merge": len(lots),
        "rows_held_back": len(held),
        "fixes": dict(report),
        "examples": {k: sorted(v)[:8] for k, v in variants.items()},
        "held_back": [{"row_id": h["row_id"], "product": h["product_name"], "reason": h["hold_reason"]} for h in held],
        "rows_without_photo": sum(not r["has_photo"] for r in rows),
        "rows_without_battery_reading": sum(r["battery_health"] is None for r in rows),
        "locked_units": sum(i["quantity"] for i in sellable if i["lock"] in ("iCloud locked", "MDM locked")),
    }
    return lots, quality


def summary(lot):
    if not lot["battery_min"]:
        bat = "battery not measured"
    elif lot["battery_min"] == lot["battery_max"]:
        bat = f"battery {lot['battery_min']}%"
    else:
        bat = f"battery {lot['battery_min']}–{lot['battery_max']}%"
    parts = [f"{lot['brand']} {lot['model']} {lot['storage_gb']}GB {lot['colour']}",
             f"Grade {lot['grade']}", lot["lock"], bat,
             f"{lot['quantity']} unit{'s' if lot['quantity'] != 1 else ''}", f"avg €{lot['avg_unit_price_eur']:.0f}"]
    if lot["functionality"] != "Working":
        parts.insert(2, lot["functionality"].lower())
    return " · ".join(parts)
