#!/usr/bin/env python3
"""
build_index.py - Build and maintain the Chroma vector index for catalog parts

Reads components from MongoDB 'catalog_parts', formats them into sentences
(excluding price), computes hashes, and incrementally embeds/indexes them
into the Chroma collection 'parts_nomic_v1' using nomic-embed-text via Ollama.

Usage:
    python build_index.py
"""

import hashlib
import os
import re
import time
from pathlib import Path
from typing import Optional

import chromadb
from dotenv import load_dotenv
from pymongo import MongoClient

import embeddings

# Configuration
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017/PC")
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = "parts_nomic_v1"
BATCH_SIZE = 64


# ─── 1. TEXT AND METADATA BUILDERS ─────────────────────────────────────────────
def describe(doc: dict) -> str:
    """
    Format a component document into a concise descriptive sentence for vector search.
    Numbers like price are explicitly omitted because numbers embed poorly and distort similarity.
    """
    cat = doc.get("category", "")
    name = doc.get("name", "Unknown Component")

    if cat == "processor":
        cores = doc.get("core_count") or doc.get("cores")
        socket = doc.get("socket")
        tdp = doc.get("tdp")
        arch = doc.get("microarchitecture")
        parts = [name, "desktop processor"]
        if cores:
            parts.append(f"{cores} cores")
        if socket:
            parts.append(f"{socket} socket")
        if tdp:
            parts.append(f"{tdp}W TDP")
        if arch:
            parts.append(f"{arch} architecture")
        return ", ".join(parts) + "."

    elif cat == "motherboard":
        socket = doc.get("socket")
        ff = doc.get("form_factor") or doc.get("formFactor")
        ram_type = doc.get("ram_type") or doc.get("ramType")
        parts = [name, "motherboard"]
        if socket:
            parts.append(f"{socket} socket")
        if ff:
            parts.append(f"{ff} form factor")
        if ram_type:
            parts.append(f"{ram_type} memory support")
        return ", ".join(parts) + "."

    elif cat == "gpu":
        chipset = doc.get("chipset")
        mem = doc.get("memory")
        length = doc.get("length")
        parts = [name, "graphics card"]
        if chipset and chipset not in name:
            parts.append(chipset)
        if mem:
            mem_val = int(mem) if isinstance(mem, (int, float)) and mem == int(mem) else mem
            parts.append(f"{mem_val} GB VRAM")
        if length:
            parts.append(f"{length} mm length")
        return ", ".join(parts) + "."

    elif cat == "ram":
        ram_type = doc.get("ram_type") or doc.get("ramType")
        cap = doc.get("capacity_gb")
        spd = doc.get("speed_mhz")
        parts = [name, "RAM memory kit"]
        if cap:
            parts.append(f"{cap} GB")
        if ram_type:
            parts.append(ram_type)
        if spd:
            parts.append(f"{spd} MHz")
        return ", ".join(parts) + "."

    elif cat == "ps":
        cap = doc.get("capacity")
        ff = doc.get("form_factor")
        interface = doc.get("interface")
        parts = [name, "internal solid state drive (SSD)"]
        if cap:
            parts.append(f"{cap} GB")
        if ff:
            parts.append(f"{ff} form factor")
        if interface:
            parts.append(f"{interface} interface")
        return ", ".join(parts) + "."

    elif cat == "ss":
        cap = doc.get("capacity")
        rpm = doc.get("rpm")
        parts = [name, "internal hard disk drive (HDD)"]
        if cap:
            parts.append(f"{cap} GB" if cap < 1000 else f"{cap // 1000} TB")
        if rpm:
            parts.append(f"{rpm} RPM")
        return ", ".join(parts) + "."

    elif cat == "psu":
        w = doc.get("wattage")
        eff = doc.get("efficiency") or doc.get("rating")
        parts = [name, "power supply (PSU)"]
        if w:
            parts.append(f"{w}W")
        if eff:
            parts.append(eff)
        return ", ".join(parts) + "."

    elif cat == "cabinet":
        t = doc.get("type")
        c = doc.get("color")
        parts = [name, "PC cabinet case"]
        if t:
            parts.append(t)
        if c:
            parts.append(f"{c} color")
        return ", ".join(parts) + "."

    elif cat == "cooling":
        sz = doc.get("size")
        c = doc.get("color")
        parts = [name, "CPU cooler"]
        if sz:
            parts.append(f"{sz} mm")
        if c:
            parts.append(f"{c} color")
        return ", ".join(parts) + "."

    return f"{name} component."


def build_metadata(doc: dict, doc_hash: Optional[str] = None) -> dict:
    """
    Construct a clean metadata dict containing only valid simple types (str, int, float, bool)
    and strictly omitting any missing/None/empty values.
    """
    meta = {}

    if doc.get("category"):
        meta["category"] = str(doc["category"])

    price = doc.get("price_inr") if doc.get("price_inr") is not None else doc.get("price")
    if price is not None:
        try:
            meta["price"] = float(price)
        except (ValueError, TypeError):
            pass

    meta["in_stock"] = bool(doc.get("in_stock", True))

    if doc.get("source"):
        meta["source"] = str(doc["source"])

    if doc_hash:
        meta["doc_hash"] = str(doc_hash)

    # Hardware & compatibility filter keys
    socket = doc.get("socket")
    if socket:
        meta["socket"] = str(socket)

    ram_type = doc.get("ram_type") or doc.get("ramType")
    if ram_type:
        meta["ram_type"] = str(ram_type)

    form_factor = doc.get("form_factor") or doc.get("formFactor")
    if form_factor:
        meta["form_factor"] = str(form_factor)

    for int_key in ["wattage", "capacity_gb", "speed_mhz"]:
        val = doc.get(int_key)
        if val is not None:
            try:
                meta[int_key] = int(val)
            except (ValueError, TypeError):
                pass

    cap_val = doc.get("capacity")
    if cap_val is not None and isinstance(cap_val, (int, float)):
        meta["capacity"] = int(cap_val)

    for float_key in ["tdp", "length"]:
        val = doc.get(float_key)
        if val is not None:
            try:
                meta[float_key] = float(val)
            except (ValueError, TypeError):
                pass

    for str_key in ["chipset", "efficiency"]:
        val = doc.get(str_key) or (doc.get("rating") if str_key == "efficiency" else None)
        if val:
            meta[str_key] = str(val)

    return meta


def compute_doc_hash(text: str) -> str:
    """Compute deterministic short hash of description text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ─── 2. CHROMA & MONGO CONNECTION ─────────────────────────────────────────────
def get_chroma_client() -> chromadb.ClientAPI:
    """Connect to Chroma via HTTP server, falling back to persistent directory if unavailable."""
    try:
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        client.heartbeat()
        return client
    except Exception:
        fallback_path = str(BASE_DIR / "data" / "chroma")
        return chromadb.PersistentClient(path=fallback_path)


def get_collection(client: chromadb.ClientAPI) -> chromadb.Collection:
    """Get or create the target parts collection with cosine similarity space."""
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# ─── 3. SYNC INDEX FUNCTION ───────────────────────────────────────────────────
def sync_index(mongo_uri: str = MONGODB_URI) -> dict:
    """
    Synchronize the Chroma index with the MongoDB catalog_parts collection.
    Only embeds new or modified items; deletes removed items; skips identical items.
    """
    start_time = time.time()
    print("=" * 60)
    print("CHROMA VECTOR INDEX SYNCHRONIZATION (DAY 6)")
    print(f"Collection : {COLLECTION_NAME}")
    print(f"MongoDB URI: {mongo_uri}")
    print("=" * 60)

    # 1. Fetch Mongo documents
    mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = mongo_client.get_database()
    if db.name in ("admin", "test", "") or db.name is None:
        db = mongo_client["PC"]

    collection_parts = db["catalog_parts"]
    mongo_docs = list(collection_parts.find({}))
    print(f"Loaded {len(mongo_docs)} components from MongoDB 'catalog_parts'.")

    # 2. Connect to Chroma
    chroma_client = get_chroma_client()
    chroma_coll = get_collection(chroma_client)

    # 3. Fetch existing Chroma items (IDs and hashes)
    existing = chroma_coll.get(include=["metadatas"])
    existing_hashes = {}
    if existing and existing.get("ids"):
        for id_, meta in zip(existing["ids"], existing["metadatas"]):
            existing_hashes[id_] = meta.get("doc_hash") if meta else None

    print(f"Chroma currently holds {len(existing_hashes)} indexed parts.")

    # 4. Prune stale documents
    mongo_ids = {str(d["_id"]) for d in mongo_docs}
    stale_ids = [id_ for id_ in existing_hashes if id_ not in mongo_ids]
    if stale_ids:
        print(f"Pruning {len(stale_ids)} stale components from Chroma...")
        chroma_coll.delete(ids=stale_ids)

    # 5. Classify parts to process
    prepared_items = []
    new_items = []
    changed_items = []
    skipped_count = 0

    for doc in mongo_docs:
        doc_id = str(doc["_id"])
        text = describe(doc)
        text_hash = compute_doc_hash(text)
        meta = build_metadata(doc, doc_hash=text_hash)

        item = {
            "id": doc_id,
            "text": text,
            "hash": text_hash,
            "metadata": meta,
        }
        prepared_items.append(item)

        if doc_id not in existing_hashes:
            new_items.append(item)
        elif existing_hashes.get(doc_id) != text_hash:
            changed_items.append(item)
        else:
            skipped_count += 1

    to_embed = new_items + changed_items
    print(f"Analysis:")
    print(f"  • New items to embed    : {len(new_items)}")
    print(f"  • Changed items to embed: {len(changed_items)}")
    print(f"  • Skipped (unchanged)   : {skipped_count}")
    print(f"  • Deleted (stale)       : {len(stale_ids)}")

    # 6. Embed and Upsert in Batches
    if to_embed:
        print(f"\nEmbedding and indexing {len(to_embed)} components in batches of {BATCH_SIZE}...")
        for i in range(0, len(to_embed), BATCH_SIZE):
            batch = to_embed[i:i + BATCH_SIZE]
            batch_texts = [it["text"] for it in batch]
            batch_ids = [it["id"] for it in batch]
            batch_metas = [it["metadata"] for it in batch]

            batch_embs = embeddings.embed_documents(batch_texts, batch_size=BATCH_SIZE)

            chroma_coll.upsert(
                ids=batch_ids,
                embeddings=batch_embs,
                documents=batch_texts,
                metadatas=batch_metas,
            )
            print(f"  Processed {min(i + BATCH_SIZE, len(to_embed))}/{len(to_embed)} parts...")
    else:
        print("\nIndex is completely up to date. No embedding calls needed.")

    duration = time.time() - start_time
    final_count = chroma_coll.count()
    print("\n" + "=" * 60)
    print(f"SYNC COMPLETED in {duration:.2f} seconds")
    print(f"  • Chroma Collection Count: {final_count}")
    print(f"  • Mongo Parts Count      : {len(mongo_docs)}")
    print("=" * 60)

    return {
        "new": len(new_items),
        "changed": len(changed_items),
        "skipped": skipped_count,
        "deleted": len(stale_ids),
        "chroma_count": final_count,
        "mongo_count": len(mongo_docs),
        "duration": duration,
    }


if __name__ == "__main__":
    sync_index()
