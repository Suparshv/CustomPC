#!/usr/bin/env python3
"""
build_index.py - Build and maintain the Chroma vector index for catalog parts

Reads components from MongoDB 'catalog_parts', formats them into sentences
(excluding price), computes hashes, and incrementally embeds/indexes them
into the Chroma collection 'parts_nomic_v1' using nomic-embed-text via Ollama.

Features:
- Separate document hash (model:text) and metadata hash (price, stock, etc.).
- Instant zero-cost metadata update when only price/stock changes in MongoDB.
- Safety guards against empty MongoDB collections and mass accidental deletions.
- Strict connection check requiring explicit CHROMA_ALLOW_FALLBACK=1 for local directory fallback.
- Natural descriptions distinguishing air coolers from liquid (AIO) coolers.

Usage:
    python build_index.py
"""

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

import chromadb
from dotenv import load_dotenv
from pymongo import MongoClient

import embeddings

logger = logging.getLogger(__name__)

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
        mem = doc.get("gpu_memory") if doc.get("gpu_memory") is not None else doc.get("memory")
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
        t = doc.get("case_type") or doc.get("type")
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
        cooler_kind = doc.get("cooler_kind")
        if not cooler_kind:
            name_lower = name.lower()
            cooler_kind = "liquid" if sz is not None or "aio" in name_lower or "liquid" in name_lower else "air"

        if cooler_kind == "liquid":
            rad = f", {sz} mm radiator" if sz else ""
            desc_type = f"liquid (AIO) CPU cooler{rad}"
        else:
            desc_type = "air CPU cooler"

        parts = [name, desc_type]
        if c:
            parts.append(f"{c} color")
        return ", ".join(parts) + "."

    return f"{name} component."


def build_metadata(
    doc: dict,
    doc_hash: Optional[str] = None,
    meta_hash: Optional[str] = None,
) -> dict:
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

    if meta_hash:
        meta["meta_hash"] = str(meta_hash)

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

    # Extended filter attributes (Day 8 preparation)
    if doc.get("cooler_kind"):
        meta["cooler_kind"] = str(doc["cooler_kind"])
    elif doc.get("category") == "cooling":
        meta["cooler_kind"] = "liquid" if doc.get("size") is not None else "air"

    case_t = doc.get("case_type") or doc.get("type")
    if case_t and doc.get("category") == "cabinet":
        meta["case_type"] = str(case_t)

    gpu_mem = doc.get("gpu_memory") if doc.get("gpu_memory") is not None else doc.get("memory")
    if gpu_mem is not None and doc.get("category") == "gpu":
        try:
            meta["gpu_memory"] = float(gpu_mem)
        except (ValueError, TypeError):
            pass

    return meta


def compute_doc_hash(text: str, model: str = embeddings.DEFAULT_MODEL) -> str:
    """Compute deterministic short hash of model name and description text."""
    payload = f"{model}:{text.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compute_meta_hash(metadata: dict) -> str:
    """
    Compute deterministic short hash of metadata values, excluding hash fields.
    Allows zero-cost detection of price or stock changes without re-embedding.
    """
    clean = {k: v for k, v in metadata.items() if k not in ("doc_hash", "meta_hash")}
    payload = json.dumps(clean, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ─── 2. CHROMA & MONGO CONNECTION ─────────────────────────────────────────────
def get_chroma_client() -> chromadb.ClientAPI:
    """Connect to Chroma via HTTP server. Fails loudly if unreachable unless explicit fallback is enabled."""
    try:
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        client.heartbeat()
        return client
    except Exception as exc:
        allow_fallback = os.getenv("CHROMA_ALLOW_FALLBACK", "0").lower() in ("1", "true", "yes")
        fallback_path = str(BASE_DIR / "data" / "chroma")
        if allow_fallback:
            print("\n" + "!" * 70)
            print(f"WARNING: Chroma HTTP server at {CHROMA_HOST}:{CHROMA_PORT} is unreachable ({exc})!")
            print(f"Falling back to local PersistentClient at '{fallback_path}' because CHROMA_ALLOW_FALLBACK=1.")
            print("!" * 70 + "\n")
            return chromadb.PersistentClient(path=fallback_path)
        else:
            raise ConnectionError(
                f"Failed to connect to Chroma server at {CHROMA_HOST}:{CHROMA_PORT}: {exc}\n"
                f"To start Chroma server, run:\n"
                f"    chroma run --path ./agent-service/data/chroma --port {CHROMA_PORT}\n"
                f"Or set CHROMA_ALLOW_FALLBACK=1 in .env to explicitly allow fallback to local PersistentClient."
            ) from exc


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
    - Re-embeds only when description text changes or document is new.
    - Updates metadata without re-embedding when only price/stock/specs change.
    - Aborts if MongoDB returns 0 documents (empty collection guard).
    - Aborts if >50% of existing index would be deleted (mass deletion guard).
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

    # Safety Guard 1: Empty collection check
    if len(mongo_docs) == 0:
        raise RuntimeError(
            "MongoDB 'catalog_parts' collection returned 0 documents! "
            "Aborting sync to prevent wiping the entire Chroma index. "
            "Please ensure MongoDB is running and 'python ingest_parts.py' has executed."
        )

    # 2. Connect to Chroma
    chroma_client = get_chroma_client()
    chroma_coll = get_collection(chroma_client)

    # 3. Fetch existing Chroma items (IDs and hashes)
    existing = chroma_coll.get(include=["metadatas"])
    existing_items = {}
    if existing and existing.get("ids"):
        for id_, meta in zip(existing["ids"], existing["metadatas"]):
            if meta:
                existing_items[id_] = (meta.get("doc_hash"), meta.get("meta_hash"))
            else:
                existing_items[id_] = (None, None)

    print(f"Chroma currently holds {len(existing_items)} indexed parts.")

    # 4. Prune stale documents
    mongo_ids = {str(d["_id"]) for d in mongo_docs}
    stale_ids = [id_ for id_ in existing_items if id_ not in mongo_ids]

    # Safety Guard 2: Mass deletion guard (>50% of collection)
    if len(existing_items) > 10 and len(stale_ids) > 0.5 * len(existing_items):
        allow_mass_del = os.getenv("ALLOW_MASS_DELETION", "0").lower() in ("1", "true", "yes")
        if not allow_mass_del:
            raise RuntimeError(
                f"Mass deletion guard triggered! Sync would delete {len(stale_ids)} of {len(existing_items)} "
                f"parts ({len(stale_ids)/len(existing_items):.1%}) from Chroma.\n"
                f"If this mass deletion is intentional, re-run with ALLOW_MASS_DELETION=1."
            )

    if stale_ids:
        print(f"Pruning {len(stale_ids)} stale components from Chroma...")
        chroma_coll.delete(ids=stale_ids)

    # 5. Classify parts to process
    new_items = []
    text_changed_items = []
    meta_only_items = []
    skipped_count = 0

    for doc in mongo_docs:
        doc_id = str(doc["_id"])
        text = describe(doc)
        text_hash = compute_doc_hash(text)

        # Build base metadata, then compute meta_hash before adding hash keys
        base_meta = build_metadata(doc)
        meta_h = compute_meta_hash(base_meta)
        base_meta["doc_hash"] = text_hash
        base_meta["meta_hash"] = meta_h

        item = {
            "id": doc_id,
            "text": text,
            "doc_hash": text_hash,
            "meta_hash": meta_h,
            "metadata": base_meta,
        }

        if doc_id not in existing_items:
            new_items.append(item)
        else:
            old_doc_hash, old_meta_hash = existing_items[doc_id]
            if old_doc_hash != text_hash:
                text_changed_items.append(item)
            elif old_meta_hash != meta_h:
                meta_only_items.append(item)
            else:
                skipped_count += 1

    to_embed = new_items + text_changed_items
    print(f"Analysis:")
    print(f"  • New items to embed          : {len(new_items)}")
    print(f"  • Description changed (embed) : {len(text_changed_items)}")
    print(f"  • Metadata only changed (fast): {len(meta_only_items)}")
    print(f"  • Skipped (identical)         : {skipped_count}")
    print(f"  • Deleted (stale)             : {len(stale_ids)}")

    # 6. Fast Path: Update metadata only without re-embedding
    if meta_only_items:
        print(f"\nUpdating metadata for {len(meta_only_items)} components without re-embedding...")
        for i in range(0, len(meta_only_items), BATCH_SIZE):
            batch = meta_only_items[i:i + BATCH_SIZE]
            batch_ids = [it["id"] for it in batch]
            batch_metas = [it["metadata"] for it in batch]
            chroma_coll.update(
                ids=batch_ids,
                metadatas=batch_metas,
            )
        print(f"  Metadata update complete.")

    # 7. Embed and Upsert in Batches
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
        print("\nNo embedding calls needed.")

    duration = time.time() - start_time
    final_count = chroma_coll.count()
    print("\n" + "=" * 60)
    print(f"SYNC COMPLETED in {duration:.2f} seconds")
    print(f"  • Chroma Collection Count: {final_count}")
    print(f"  • Mongo Parts Count      : {len(mongo_docs)}")
    print("=" * 60)

    return {
        "new": len(new_items),
        "text_changed": len(text_changed_items),
        "meta_only": len(meta_only_items),
        "skipped": skipped_count,
        "deleted": len(stale_ids),
        "chroma_count": final_count,
        "mongo_count": len(mongo_docs),
        "duration": duration,
    }


if __name__ == "__main__":
    sync_index()
