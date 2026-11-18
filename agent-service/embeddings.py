"""
embeddings.py - Embedding utilities for nomic-embed-text via Ollama

Handles text prefixing (search_document: and search_query:), batching (default: 64),
and retry logic for Ollama embedding API operations.
"""

import os
import time
import logging
from typing import Optional

import ollama

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "nomic-embed-text"
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "
DEFAULT_BATCH_SIZE = 64
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


def format_doc_text(text: str) -> str:
    """Ensure search_document: prefix is applied exactly once."""
    clean = text.strip()
    if clean.startswith(DOC_PREFIX):
        return clean
    return f"{DOC_PREFIX}{clean}"


def format_query_text(query: str) -> str:
    """Ensure search_query: prefix is applied exactly once."""
    clean = query.strip()
    if clean.startswith(QUERY_PREFIX):
        return clean
    return f"{QUERY_PREFIX}{clean}"


# 127.0.0.1, not "localhost": on Windows "localhost" tries IPv6 (::1) first, Ollama only
# listens on IPv4, and every NEW connection then waits ~2 s before falling back.
# Measured 18 Nov: ~2,100 ms per embedding via localhost vs ~50 ms via 127.0.0.1.
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"

# One client (= one reusable HTTP connection) per host, instead of a new one per search.
_CLIENTS: dict = {}


def get_ollama_client(host: Optional[str] = None) -> ollama.Client:
    """Get the shared Ollama client for a host (from the parameter, OLLAMA_HOST, or the default)."""
    ollama_host = host or os.getenv("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST
    if ollama_host not in _CLIENTS:
        _CLIENTS[ollama_host] = ollama.Client(host=ollama_host)
    return _CLIENTS[ollama_host]


def embed_batch_with_retry(
    texts: list[str],
    client: Optional[ollama.Client] = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = MAX_RETRIES,
    keep_alive: str = "1h",
) -> list[list[float]]:
    """Embed a single pre-formatted batch of texts with retry backoff."""
    if not texts:
        return []

    ollama_client = client or get_ollama_client()
    backoff = INITIAL_BACKOFF

    for attempt in range(1, max_retries + 1):
        try:
            response = ollama_client.embed(model=model, input=texts, keep_alive=keep_alive)
            embeddings = response.get("embeddings") or response.get("embedding")
            if embeddings and len(embeddings) == len(texts):
                return embeddings
            raise ValueError(f"Expected {len(texts)} embeddings, got {len(embeddings) if embeddings else 0}")
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Failed to embed batch of {len(texts)} after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Embedding attempt {attempt} failed ({e}), retrying in {backoff}s...")
            time.sleep(backoff)
            backoff *= 2.0

    return []


def embed_documents(
    texts: list[str],
    batch_size: int = DEFAULT_BATCH_SIZE,
    client: Optional[ollama.Client] = None,
    model: str = DEFAULT_MODEL,
    keep_alive: str = "1h",
) -> list[list[float]]:
    """
    Format documents with 'search_document: ' prefix and generate embeddings in batches.
    """
    if not texts:
        return []

    formatted_texts = [format_doc_text(t) for t in texts]
    all_embeddings = []

    for i in range(0, len(formatted_texts), batch_size):
        batch = formatted_texts[i:i + batch_size]
        batch_embeddings = embed_batch_with_retry(batch, client=client, model=model, keep_alive=keep_alive)
        all_embeddings.extend(batch_embeddings)

    return all_embeddings


def embed_query(
    query: str,
    client: Optional[ollama.Client] = None,
    model: str = DEFAULT_MODEL,
    keep_alive: str = "1h",
) -> list[float]:
    """
    Format query with 'search_query: ' prefix and generate single embedding vector.
    """
    formatted = format_query_text(query)
    embeddings = embed_batch_with_retry([formatted], client=client, model=model, keep_alive=keep_alive)
    return embeddings[0]
