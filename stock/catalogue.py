"""Synthetic raw stock export, written the way a B2B reseller portal often looks:
inconsistent brand spellings, mixed grade scales, colour variants, duplicate rows.
Plus an inbound trade-in pipeline (shipments on their way from partners).

Everything is invented and seeded, so every run produces the same data.
"""
import random
from datetime import date, timedelta

TODAY = date(2026, 10, 15)

MODELS = [
    # brand, model, storage options, base price (grade A, EUR)
    ("Apple", "iPhone 11", [64, 128], 175),
    ("Apple", "iPhone 12", [64, 128], 245),
    ("Apple", "iPhone 13", [128, 256], 330),
    ("Apple", "iPhone 14", [128, 256], 410),
    ("Apple", "iPhone 15", [128], 520),
    ("Apple", "iPad 9th Gen", [64], 190),
    ("Samsung", "Galaxy S21", [128], 165),
    ("Samsung", "Galaxy S22", [128, 256], 215),
    ("Samsung", "Galaxy S23", [128], 300),
    ("Samsung", "Galaxy A54", [128], 150),
    ("Google", "Pixel 7", [128], 160),
    ("Google", "Pixel 8", [128], 260),
    ("Xiaomi", "Redmi Note 12", [128], 95),
    ("Ulefone", "Armor 21", [256], 120),
]

# How the brand shows up in the raw export
BRAND_VARIANTS = {
    "Apple": ["Apple", "APPLE", "apple", "Apple Inc."],
    "Samsung": ["Samsung", "SAMSUNG", "Samsung Electronics"],
    "Google": ["Google", "google"],
    "Xiaomi": ["Xiaomi", "XIAOMI", "Redmi"],
    "Ulefone": ["uleFone", "Ulefone", "ULEFONE"],
}

COLOURS = {
    "Black": ["Black", "black", "Midnight", "Jet Black", "Phantom Black", "Obsidian"],
    "White": ["White", "white", "Starlight", "Snow"],
    "Blue": ["Blue", "Pacific Blue", "Sierra Blue", "blue"],
    "Grey": ["Grey", "Gray", "Space Gray", "Graphite"],
    "Green": ["Green", "Alpine Green", "Mint"],
    "Red": ["(PRODUCT)RED", "Red"],
    "Purple": ["Purple", "Lavender", "Deep Purple"],
}

# Raw grade labels and how they map to a single A–D scale
RAW_GRADES = {
    "Grade A+": "A", "A+": "A", "Grade A": "A", "A": "A", "Grade AB": "B",
    "Grade B": "B", "B": "B", "Grade BC": "C", "Grade C+": "C", "Grade C": "C",
    "C": "C", "Grade D": "D", "Swap": None, "Not specified": None,
}
GRADE_FACTOR = {"A": 1.0, "B": 0.85, "C": 0.68, "D": 0.4}

LOCATIONS = ["WH1-A1", "WH1-A2", "WH1-B4", "WH2-C1", "WH2-C3"]  # WH1 main warehouse, WH2 refurbishment hub
PARTNERS = ["Kestrel Telecom", "Aurora Mobile", "Rhine Digital", "Lumen Retail", "Polaris Phones", "Fjord Connect"]


def raw_rows(seed=7, n=420):
    rng = random.Random(seed)
    rows = []
    for i in range(1, n + 1):
        brand, model, storages, base = rng.choice(MODELS)
        storage = rng.choice(storages)
        raw_grade = rng.choices(list(RAW_GRADES), weights=[3, 4, 10, 6, 6, 12, 6, 6, 5, 6, 4, 3, 2, 2])[0]
        clean_grade = RAW_GRADES[raw_grade] or "B"
        colour_group = rng.choice(list(COLOURS))
        storage_txt = rng.choice([f"{storage}GB", f"{storage} GB", f"{storage}gb"])
        name = rng.choice([f"{model} {storage_txt}", f"{model} ({storage_txt})", f"{model} {storage_txt} {colour_group}"])
        price = round(base * (1 + (storage > storages[0]) * 0.12) * GRADE_FACTOR[clean_grade] * rng.uniform(0.93, 1.07), 2)
        if rng.random() < 0.02:  # data-entry errors
            price = round(price * rng.choice([0.1, 10]), 2)
        battery = rng.randint(78, 100) if rng.random() > 0.15 else None
        lock = rng.choices(["CloudOFF", "Cloud Locked", "MDM Lock", ""], weights=[85, 5, 3, 7])[0]
        rows.append({
            "row_id": f"R{i:04d}",
            "manufacturer": rng.choice(BRAND_VARIANTS[brand]),
            "product_name": name,
            "appearance": raw_grade,
            "functionality": rng.choices(["Working", "Minor Fault"], weights=[94, 6])[0],
            "colour": rng.choice(COLOURS[colour_group]),
            "cloud_lock": lock,
            "boxed": rng.choice(["Unboxed", "Original Box", "Damaged Box", "Unboxed"]),
            "battery_health": battery,
            "quantity": rng.choice([1, 1, 2, 3, 5, 8, 10, 15, 20, 40]),
            "unit_price_eur": price,
            "location": rng.choice(LOCATIONS),
            "has_photo": rng.random() > 0.37,
        })
    return rows


def inbound_shipments(seed=11, n=24):
    """Trade-in shipments on their way from partners, with expected grade mix."""
    rng = random.Random(seed)
    out = []
    for i in range(1, n + 1):
        brand, model, storages, _ = rng.choice(MODELS)
        units = rng.choice([20, 40, 60, 80, 120, 200])
        a = rng.uniform(0.15, 0.4)
        b = rng.uniform(0.3, 0.45)
        c = max(0.05, 1 - a - b - 0.08)
        out.append({
            "shipment_id": f"IN-{2600 + i}",
            "partner": rng.choice(PARTNERS),
            "brand": brand,
            "model": model,
            "storage_gb": rng.choice(storages),
            "units": units,
            "expected_grade_mix": {"A": round(a, 2), "B": round(b, 2), "C": round(c, 2), "D": round(1 - a - b - c, 2)},
            "eta": str(TODAY + timedelta(days=rng.randint(1, 30))),
            "status": rng.choice(["Booked", "In transit", "In transit", "At customs"]),
        })
    return out
