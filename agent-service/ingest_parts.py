#!/usr/bin/env python3
"""
ingest_parts.py - Ingest PC Component Catalog into MongoDB

Loads ~2,900 real PC components (target: 2,861 from docyx/pc-part-dataset
plus 24 seed parts from componentSpecs.json) into the 'catalog_parts' collection
in MongoDB database 'PC'.

Usage:
    python ingest_parts.py
"""

import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient, ReplaceOne

# Paths
BASE_DIR = Path(__file__).resolve().parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
SEED_SPECS_PATH = BASE_DIR.parent / "backend" / "data" / "componentSpecs.json"
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017/PC")
USD_TO_INR_RATE = float(os.getenv("USD_TO_INR_RATE", "93.0"))
USD_TO_INR_DATE = os.getenv("USD_TO_INR_DATE", "2026-11-12")


def generate_stable_id(prefix: str, raw_item: dict) -> str:
    """Generate a deterministic, clean 12-hex hash ID from category prefix and part attributes."""
    sig = json.dumps(raw_item, sort_keys=True)
    digest = hashlib.sha256(sig.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def is_simulated_in_stock(part_id: str) -> bool:
    """Deterministically simulate ~92% in-stock status using the part ID."""
    h = int(hashlib.md5(f"stock:{part_id}".encode("utf-8")).hexdigest(), 16)
    return (h % 100) < 92


def spread_sample(items: list[dict], max_items: int) -> list[dict]:
    """
    Pick a spread of parts across the price range for a group rather than just the cheapest.
    If len(items) <= max_items, returns all items.
    Otherwise, picks max_items evenly spaced across sorted prices.
    """
    if len(items) <= max_items:
        return items
    items_sorted = sorted(items, key=lambda x: (x.get("price") or 0.0))
    if max_items == 1:
        return [items_sorted[len(items_sorted) // 2]]
    step = (len(items_sorted) - 1) / (max_items - 1)
    indices = [round(i * step) for i in range(max_items)]
    return [items_sorted[idx] for idx in sorted(set(indices))]


# ─── 1. SEED PARTS (24 items) ──────────────────────────────────────────────────
def load_seed_parts() -> list[dict]:
    if not SEED_SPECS_PATH.exists():
        raise FileNotFoundError(f"Seed specifications not found at: {SEED_SPECS_PATH}")

    with open(SEED_SPECS_PATH, "r", encoding="utf-8") as f:
        specs = json.load(f)

    seed_docs = []
    for key, spec in specs.items():
        doc = {
            "_id": key.strip(),
            "name": spec.get("name"),
            "category": spec.get("category"),
            "source": "seed24",
            "price_inr": spec.get("price"),
            "price_inr_approx": False,
            "in_stock": True,
            "stock_simulated": True,
        }
        # Copy remaining category-specific metadata
        for k, v in spec.items():
            if k not in ("name", "category", "price"):
                doc[k] = v
        seed_docs.append(doc)
    return seed_docs


# ─── 2. CPU INGESTION ──────────────────────────────────────────────────────────
def load_cpus() -> list[dict]:
    with open(RAW_DATA_DIR / "cpu.json", "r", encoding="utf-8") as f:
        raw_cpus = json.load(f)

    docs = []
    for c in raw_cpus:
        price = c.get("price")
        if not price or price <= 0:
            continue
        name = c.get("name", "")
        arch = c.get("microarchitecture") or ""

        # Derive socket: Ryzen 3000-5000 -> AM4, Ryzen 7000-9000 -> AM5,
        # Intel 12th-14th -> LGA1700, Core Ultra (Arrow Lake) -> LGA1851
        socket = None
        if re.search(r"Ryzen \d\s+(3\d{3}|4\d{3}|5\d{3})", name):
            socket = "AM4"
        elif re.search(r"Ryzen \d\s+(7\d{3}|8\d{3}|9\d{3})", name):
            socket = "AM5"
        elif re.search(r"i[3579]-(12\d{3}|13\d{3}|14\d{3})", name):
            socket = "LGA1700"
        elif "Core Ultra" in name or "Arrow Lake" in arch:
            socket = "LGA1851"

        if not socket:
            continue

        part_id = generate_stable_id("cpu", c)
        docs.append({
            "_id": part_id,
            "name": name,
            "category": "processor",
            "source": "pcpartpicker",
            "price_usd": float(price),
            "price_inr": round(float(price) * USD_TO_INR_RATE),
            "price_inr_approx": True,
            "in_stock": is_simulated_in_stock(part_id),
            "stock_simulated": True,
            "socket": socket,
            "core_count": c.get("core_count"),
            "core_clock": c.get("core_clock"),
            "boost_clock": c.get("boost_clock"),
            "tdp": c.get("tdp"),
            "microarchitecture": arch,
            "graphics": c.get("graphics"),
        })
    return docs


# ─── 3. MOTHERBOARD INGESTION ─────────────────────────────────────────────────
def load_motherboards() -> list[dict]:
    with open(RAW_DATA_DIR / "motherboard.json", "r", encoding="utf-8") as f:
        raw_mbs = json.load(f)

    docs = []
    for m in raw_mbs:
        price = m.get("price")
        if not price or price <= 0:
            continue
        socket = m.get("socket")
        name = m.get("name", "")

        # Derive RAM type: AM5 & LGA1851 -> DDR5, AM4 -> DDR4
        # LGA1700 boards require DDR4 / D4 in name, or ASRock H610M-HDV/M.2+ D5 for DDR5
        ram_type = None
        if socket == "AM4":
            ram_type = "DDR4"
        elif socket in ("AM5", "LGA1851"):
            ram_type = "DDR5"
        elif socket == "LGA1700":
            if re.search(r"\b(ddr4|d4)\b", name, re.IGNORECASE):
                ram_type = "DDR4"
            elif "H610M-HDV/M.2+ D5" in name:
                ram_type = "DDR5"

        if not ram_type:
            continue

        part_id = generate_stable_id("mb", m)
        docs.append({
            "_id": part_id,
            "name": name,
            "category": "motherboard",
            "source": "pcpartpicker",
            "price_usd": float(price),
            "price_inr": round(float(price) * USD_TO_INR_RATE),
            "price_inr_approx": True,
            "in_stock": is_simulated_in_stock(part_id),
            "stock_simulated": True,
            "socket": socket,
            "form_factor": m.get("form_factor"),
            "ram_type": ram_type,
            "max_memory": m.get("max_memory"),
            "memory_slots": m.get("memory_slots"),
            "color": m.get("color"),
        })
    return docs


# ─── 4. GPU INGESTION ──────────────────────────────────────────────────────────
def load_gpus(cap_per_chipset: int = 5) -> list[dict]:
    with open(RAW_DATA_DIR / "video-card.json", "r", encoding="utf-8") as f:
        raw_gpus = json.load(f)

    by_chipset = defaultdict(list)
    for g in raw_gpus:
        price = g.get("price")
        length = g.get("length")
        chipset = g.get("chipset") or ""
        if not price or price <= 0 or not length or length <= 0:
            continue

        # RTX 20-50, GTX 16, RX 6000/7000/9000
        is_recent = bool(
            re.search(r"GeForce (RTX [2345]0\d{2}|GTX 16\d{2})", chipset)
            or re.search(r"Radeon RX [679]\d{3}", chipset)
        )
        if not is_recent:
            continue

        by_chipset[chipset].append(g)

    docs = []
    for chipset, items in by_chipset.items():
        sampled = spread_sample(items, cap_per_chipset)
        for g in sampled:
            name = g.get("name", "")
            part_id = generate_stable_id("gpu", g)
            docs.append({
                "_id": part_id,
                "name": f"{chipset} {name}" if chipset not in name else name,
                "category": "gpu",
                "source": "pcpartpicker",
                "price_usd": float(g["price"]),
                "price_inr": round(float(g["price"]) * USD_TO_INR_RATE),
                "price_inr_approx": True,
                "in_stock": is_simulated_in_stock(part_id),
                "stock_simulated": True,
                "chipset": g.get("chipset"),
                "memory": g.get("memory"),
                "core_clock": g.get("core_clock"),
                "boost_clock": g.get("boost_clock"),
                "length": g.get("length"),
                "color": g.get("color"),
            })
    return docs


# ─── 5. RAM INGESTION ──────────────────────────────────────────────────────────
def load_ram(cap_per_bucket: int = 30) -> list[dict]:
    with open(RAW_DATA_DIR / "memory.json", "r", encoding="utf-8") as f:
        raw_rams = json.load(f)

    by_bucket = defaultdict(list)
    for r in raw_rams:
        price = r.get("price")
        speed = r.get("speed")
        modules = r.get("modules")
        if not price or price <= 0:
            continue
        if not isinstance(speed, list) or len(speed) < 2 or speed[0] not in (4, 5):
            continue
        if not isinstance(modules, list) or len(modules) < 2:
            continue

        gen = f"DDR{speed[0]}"
        speed_mhz = speed[1]
        capacity_gb = modules[0] * modules[1]
        if not (8 <= capacity_gb <= 128):
            continue

        r["_parsed"] = {
            "ram_type": gen,
            "speed_mhz": speed_mhz,
            "capacity_gb": capacity_gb,
        }
        by_bucket[(gen, capacity_gb)].append(r)

    docs = []
    for bucket_key, items in by_bucket.items():
        sampled = spread_sample(items, cap_per_bucket)
        for r in sampled:
            name = r.get("name", "")
            parsed = r["_parsed"]
            part_id = generate_stable_id("ram", r)
            docs.append({
                "_id": part_id,
                "name": name,
                "category": "ram",
                "source": "pcpartpicker",
                "price_usd": float(r["price"]),
                "price_inr": round(float(r["price"]) * USD_TO_INR_RATE),
                "price_inr_approx": True,
                "in_stock": is_simulated_in_stock(part_id),
                "stock_simulated": True,
                "ram_type": parsed["ram_type"],
                "capacity_gb": parsed["capacity_gb"],
                "speed_mhz": parsed["speed_mhz"],
                "modules": r.get("modules"),
                "first_word_latency": r.get("first_word_latency"),
                "cas_latency": r.get("cas_latency"),
                "color": r.get("color"),
            })
    return docs


# ─── 6. PSU INGESTION ──────────────────────────────────────────────────────────
def load_psus(cap_per_wattage: int = 15) -> list[dict]:
    with open(RAW_DATA_DIR / "power-supply.json", "r", encoding="utf-8") as f:
        raw_psus = json.load(f)

    by_wattage = defaultdict(list)
    for p in raw_psus:
        price = p.get("price")
        ptype = p.get("type")
        wattage = p.get("wattage")
        if not price or price <= 0 or ptype != "ATX" or not wattage or wattage < 450:
            continue
        by_wattage[wattage].append(p)

    docs = []
    for wattage, items in by_wattage.items():
        sampled = spread_sample(items, cap_per_wattage)
        for p in sampled:
            name = p.get("name", "")
            part_id = generate_stable_id("psu", p)
            docs.append({
                "_id": part_id,
                "name": name,
                "category": "psu",
                "source": "pcpartpicker",
                "price_usd": float(p["price"]),
                "price_inr": round(float(p["price"]) * USD_TO_INR_RATE),
                "price_inr_approx": True,
                "in_stock": is_simulated_in_stock(part_id),
                "stock_simulated": True,
                "type": p.get("type"),
                "wattage": p.get("wattage"),
                "modular": p.get("modular"),
                "efficiency": p.get("efficiency"),
                "color": p.get("color"),
            })
    return docs


# ─── 7. CABINET (CASE) INGESTION ───────────────────────────────────────────────
def load_cases(cap_per_type: int = 50) -> list[dict]:
    with open(RAW_DATA_DIR / "case.json", "r", encoding="utf-8") as f:
        raw_cases = json.load(f)

    valid_types = {
        "ATX Mid Tower",
        "MicroATX Mini Tower",
        "ATX Full Tower",
        "MicroATX Mid Tower",
        "Mini ITX Tower",
        "Mini ITX Desktop",
        "MicroATX Desktop",
        "ATX Desktop",
        "HTPC",
    }

    by_type = defaultdict(list)
    for c in raw_cases:
        price = c.get("price")
        ctype = c.get("type")
        if not price or price <= 0 or ctype not in valid_types:
            continue
        by_type[ctype].append(c)

    docs = []
    for ctype, items in by_type.items():
        sampled = spread_sample(items, cap_per_type)
        for c in sampled:
            name = c.get("name", "")
            part_id = generate_stable_id("cab", c)
            docs.append({
                "_id": part_id,
                "name": name,
                "category": "cabinet",
                "source": "pcpartpicker",
                "price_usd": float(c["price"]),
                "price_inr": round(float(c["price"]) * USD_TO_INR_RATE),
                "price_inr_approx": True,
                "in_stock": is_simulated_in_stock(part_id),
                "stock_simulated": True,
                "type": c.get("type"),
                "color": c.get("color"),
                "internal_35_bays": c.get("internal_35_bays"),
                "side_panel": c.get("side_panel"),
                "external_volume": c.get("external_volume"),
            })
    return docs


# ─── 8. STORAGE INGESTION (ps & ss) ───────────────────────────────────────────
def load_storage(cap_ssd: int = 30, cap_hdd: int = 25) -> list[dict]:
    with open(RAW_DATA_DIR / "internal-hard-drive.json", "r", encoding="utf-8") as f:
        raw_drives = json.load(f)

    ssds_by_cap = defaultdict(list)
    hdds_by_cap = defaultdict(list)

    for d in raw_drives:
        price = d.get("price")
        if not price or price <= 0:
            continue
        dtype = d.get("type")
        cap = d.get("capacity") or 0
        form_factor = d.get("form_factor")

        # Primary Storage: SSDs >= 250 GB
        if dtype == "SSD" and cap >= 250:
            ssds_by_cap[cap].append(d)
        # Secondary Storage: 3.5" HDDs
        elif form_factor in (3.5, "3.5"):
            hdds_by_cap[cap].append(d)

    docs = []
    # Primary Storage (ps)
    for cap, items in ssds_by_cap.items():
        sampled = spread_sample(items, cap_ssd)
        for d in sampled:
            name = d.get("name", "")
            part_id = generate_stable_id("ps", d)
            docs.append({
                "_id": part_id,
                "name": name,
                "category": "ps",
                "source": "pcpartpicker",
                "price_usd": float(d["price"]),
                "price_inr": round(float(d["price"]) * USD_TO_INR_RATE),
                "price_inr_approx": True,
                "in_stock": is_simulated_in_stock(part_id),
                "stock_simulated": True,
                "type": "SSD",
                "capacity": d.get("capacity"),
                "form_factor": d.get("form_factor"),
                "interface": d.get("interface"),
            })

    # Secondary Storage (ss)
    for cap, items in hdds_by_cap.items():
        sampled = spread_sample(items, cap_hdd)
        for d in sampled:
            name = d.get("name", "")
            part_id = generate_stable_id("ss", d)
            docs.append({
                "_id": part_id,
                "name": name,
                "category": "ss",
                "source": "pcpartpicker",
                "price_usd": float(d["price"]),
                "price_inr": round(float(d["price"]) * USD_TO_INR_RATE),
                "price_inr_approx": True,
                "in_stock": is_simulated_in_stock(part_id),
                "stock_simulated": True,
                "type": "HDD",
                "capacity": d.get("capacity"),
                "form_factor": d.get("form_factor"),
                "interface": d.get("interface"),
                "rpm": d.get("rpm"),
            })
    return docs


# ─── 9. COOLING INGESTION ──────────────────────────────────────────────────────
def load_coolers(cap_per_size: int = 40) -> list[dict]:
    with open(RAW_DATA_DIR / "cpu-cooler.json", "r", encoding="utf-8") as f:
        raw_coolers = json.load(f)

    by_size = defaultdict(list)
    for c in raw_coolers:
        price = c.get("price")
        if not price or price <= 0:
            continue
        size = c.get("size")
        by_size[size].append(c)

    docs = []
    for size, items in by_size.items():
        sampled = spread_sample(items, cap_per_size)
        for c in sampled:
            name = c.get("name", "")
            part_id = generate_stable_id("cool", c)
            docs.append({
                "_id": part_id,
                "name": name,
                "category": "cooling",
                "source": "pcpartpicker",
                "price_usd": float(c["price"]),
                "price_inr": round(float(c["price"]) * USD_TO_INR_RATE),
                "price_inr_approx": True,
                "in_stock": is_simulated_in_stock(part_id),
                "stock_simulated": True,
                "rpm": c.get("rpm"),
                "noise_level": c.get("noise_level"),
                "color": c.get("color"),
                "size": c.get("size"),
            })
    return docs


# ─── MAIN EXECUTION ────────────────────────────────────────────────────────────
def ingest():
    print("=" * 60)
    print("PC COMPONENT CATALOG INGESTION (DAY 5)")
    print(f"MongoDB URI : {MONGODB_URI}")
    print(f"USD->INR    : {USD_TO_INR_RATE} (effective: {USD_TO_INR_DATE})")
    print("=" * 60)

    # 1. Connect
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.server_info()  # Trigger connection check

    db = client.get_database()
    if db.name in ("admin", "test", "") or db.name is None:
        db = client["PC"]

    collection = db["catalog_parts"]

    # 2. Collect parts
    seed_parts = load_seed_parts()
    cpus = load_cpus()
    mbs = load_motherboards()
    gpus = load_gpus(cap_per_chipset=5)
    rams = load_ram(cap_per_bucket=30)
    psus = load_psus(cap_per_wattage=15)
    cases = load_cases(cap_per_type=50)
    storage = load_storage(cap_ssd=30, cap_hdd=25)
    coolers = load_coolers(cap_per_size=40)

    dataset_parts = cpus + mbs + gpus + rams + psus + cases + storage + coolers

    # Deduplicate dataset parts by _id (if any duplicate rows in raw scrape)
    unique_dataset = {}
    for d in dataset_parts:
        if d["_id"] not in unique_dataset:
            unique_dataset[d["_id"]] = d
    dataset_parts = list(unique_dataset.values())

    all_parts = seed_parts + dataset_parts

    print(f"\nCollected Component Counts:")
    print(f"  • Seed parts (source: seed24)   : {len(seed_parts):>4}")
    print(f"  • CPUs (processor)               : {len(cpus):>4}")
    print(f"  • Motherboards (motherboard)     : {len(mbs):>4}")
    print(f"  • GPUs (gpu)                     : {len(gpus):>4}")
    print(f"  • Memory (ram)                   : {len(rams):>4}")
    print(f"  • Power Supplies (psu)           : {len(psus):>4}")
    print(f"  • Cabinets (cabinet)             : {len(cases):>4}")
    print(f"  • Storage (ps + ss)              : {len(storage):>4}")
    print(f"  • Cooling (cooling)              : {len(coolers):>4}")
    print(f"  -------------------------------------")
    print(f"  Dataset Total (Unique)           : {len(dataset_parts):>4}")
    print(f"  Grand Total (Dataset + Seed)     : {len(all_parts):>4}\n")

    # 3. Create Indexes
    print("Ensuring indexes on 'category' and 'source'...")
    collection.create_index([("category", ASCENDING)])
    collection.create_index([("source", ASCENDING)])

    # 4. Bulk Upsert using ReplaceOne(..., upsert=True)
    print(f"Executing bulk upsert of {len(all_parts)} documents...")
    operations = [
        ReplaceOne({"_id": doc["_id"]}, doc, upsert=True)
        for doc in all_parts
    ]

    result = collection.bulk_write(operations, ordered=False)

    print("\nBulk Write Results:")
    print(f"  • Matched Count  : {result.matched_count}")
    print(f"  • Modified Count : {result.modified_count}")
    print(f"  • Upserted Count : {len(result.upserted_ids)}")
    print(f"  • Inserted Count : {result.inserted_count}")

    # 5. Verify Database State
    total_in_db = collection.count_documents({})
    seed_in_db = collection.count_documents({"source": "seed24"})
    dataset_in_db = collection.count_documents({"source": "pcpartpicker"})
    print(f"\nFinal MongoDB Verification:")
    print(f"  • Total documents in 'catalog_parts': {total_in_db}")
    print(f"  • Seed documents                    : {seed_in_db}")
    print(f"  • Dataset documents                 : {dataset_in_db}")
    print("=" * 60)

    return {
        "total_documents": total_in_db,
        "dataset_count": dataset_in_db,
        "seed_count": seed_in_db,
        "upserted_count": len(result.upserted_ids),
        "matched_count": result.matched_count,
    }


if __name__ == "__main__":
    ingest()
