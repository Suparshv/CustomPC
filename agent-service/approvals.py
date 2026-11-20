"""
approvals.py - Day 12: who may put an AI build in the cart.

  verdict_of   the ONE place that turns a checker result into compatible / incompatible /
               could_not_verify. A broken or missing check is never "compatible".
  ApprovalStore  SQLite table of human approvals: (thread, build hash) -> items, total,
               approved_at, expires_at, used_at. Survives a restart.
  claim_cart   the server-side cart rule: an approval must exist for this thread and this
               exact build, be unexpired and unused; then the build is re-checked against
               the catalogue NOW (same hash = same parts at the same prices; every part
               in stock). Only then are the items handed to the cart.
"""

import json
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from safety import build_hash

APPROVAL_TTL_SECONDS = 15 * 60


def verdict_of(check: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Checker result -> {"status", "problems", "unknowns"}. Anything odd -> could_not_verify."""
    if not check or "error" in check or "valid" not in check:
        reason = (check or {}).get("error") or "The compatibility checker did not run."
        return {"status": "could_not_verify", "problems": [reason], "unknowns": []}
    rules = check.get("rules") or {}
    if check.get("unresolved"):
        return {"status": "could_not_verify", "unknowns": [],
                "problems": [f"Not in the catalogue: {', '.join(map(str, check['unresolved']))}."]}
    if check.get("fails"):
        return {"status": "incompatible", "unknowns": list(check.get("unknowns") or []),
                "problems": [rules.get(r, {}).get("message", r) for r in check["fails"]]}
    unknowns = list(check.get("unknowns") or [])
    return {"status": "compatible", "problems": [], "unknowns": unknowns,
            "fully_verified": bool(check.get("fully_verified")),
            "rules_passed": len(rules) - len(unknowns), "rules_total": len(rules)}


class ApprovalStore:
    """Approval records in SQLite. Safe to share between request threads."""

    def __init__(self, path: str, clock: Callable[[], float] = time.time):
        self.clock = clock
        self._conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS approvals (
                       thread_id TEXT NOT NULL, build_hash TEXT NOT NULL,
                       items TEXT NOT NULL, total REAL NOT NULL,
                       approved_at REAL NOT NULL, expires_at REAL NOT NULL, used_at REAL,
                       PRIMARY KEY (thread_id, build_hash))""")

    def record(self, thread_id: str, build_hash_: str, items: List[Dict[str, Any]], total: float,
               ttl: float = APPROVAL_TTL_SECONDS) -> Dict[str, Any]:
        """Save an approval. An active, unused one is kept as it is (approving twice is harmless);
        a used or expired one for the same build is replaced by the new approval."""
        now = self.clock()
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO approvals (thread_id, build_hash, items, total, approved_at, expires_at, used_at)
                   VALUES (?, ?, ?, ?, ?, ?, NULL)
                   ON CONFLICT (thread_id, build_hash) DO UPDATE SET
                       items = excluded.items, total = excluded.total, approved_at = excluded.approved_at,
                       expires_at = excluded.expires_at, used_at = NULL
                   WHERE approvals.used_at IS NOT NULL OR approvals.expires_at < ?""",
                (thread_id, build_hash_, json.dumps(items), float(total), now, now + ttl, now))
        return self.get(thread_id, build_hash_)

    def get(self, thread_id: str, build_hash_: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM approvals WHERE thread_id = ? AND build_hash = ?",
                                     (thread_id, build_hash_)).fetchone()
        if row is None:
            return None
        rec = dict(row)
        rec["items"] = json.loads(rec["items"])
        return rec

    def mark_used(self, thread_id: str, build_hash_: str) -> bool:
        """True only for the FIRST caller: one approval, one cart add."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE approvals SET used_at = ? WHERE thread_id = ? AND build_hash = ? AND used_at IS NULL",
                (self.clock(), thread_id, build_hash_))
        return cur.rowcount == 1

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0]


def claim_cart(store: ApprovalStore, repo: Any, thread_id: str, build_hash_: str) -> Dict[str, Any]:
    """
    The cart rule. Returns {"status": "added", "items", "total"} or a refusal:
    not_approved | already_used | expired | build_changed | out_of_stock.
    A database outage raises (the API turns it into 503): it is never "added".
    """
    rec = store.get(thread_id, build_hash_)
    if rec is None:
        return {"status": "not_approved", "message": "This build was not approved in this chat. Approve it first."}
    if rec["used_at"] is not None:
        return {"status": "already_used", "message": "This approval was already used to add the build to the cart."}
    if store.clock() > rec["expires_at"]:
        return {"status": "expired", "message": "The approval expired (15 minutes). Ask for the build again."}

    # Re-check against the catalogue as it is NOW, not as it was when approved.
    ids = [item["id"] for item in rec["items"]]
    docs = {str(d.get("id") or d.get("_id")): d for d in repo.get_many(ids)}
    missing = [i for i in ids if i not in docs]
    if missing:
        return {"status": "build_changed", "message": f"Parts no longer in the catalogue: {', '.join(missing)}."}
    current = [{"id": i, "price": docs[i].get("price", docs[i].get("price_inr"))} for i in ids]
    try:
        same = build_hash(current) == build_hash_
    except ValueError:                       # a price is now missing: unknown, never guessed
        same = False
    if not same:
        return {"status": "build_changed",
                "message": "Prices or parts changed since you approved. Nothing was added; ask for the build again."}
    # Stock must be confirmed. Unknown stock counts as not in stock.
    # (Day 11's "swap in the next-best part" fallback is not built yet, so we only refuse.)
    gone = [item["name"] for item in rec["items"] if docs[item["id"]].get("in_stock") is not True]
    if gone:
        return {"status": "out_of_stock",
                "message": f"No longer in stock: {', '.join(gone)}. Nothing was added; ask for the build again."}
    if not store.mark_used(thread_id, build_hash_):
        return {"status": "already_used", "message": "This approval was already used to add the build to the cart."}
    return {"status": "added", "items": rec["items"], "total": rec["total"]}
