"""
repo.py - Data repository abstraction for PC parts catalog

Provides a clean interface for reading components from MongoDB
and an in-memory repository implementation for offline unit tests.
Ensures read-only access so tools never mutate or write to the database.
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017/PC")


class BasePartRepo(ABC):
    """Abstract base repository for part retrieval (read-only)."""

    @abstractmethod
    def get_one(self, part_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single part by ID."""
        pass

    @abstractmethod
    def get_many(self, part_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieve multiple parts by IDs. Missing IDs are omitted from result."""
        pass

    @abstractmethod
    def get_all(self) -> List[Dict[str, Any]]:
        """Retrieve all catalog parts."""
        pass

    @abstractmethod
    def get_by_filter(self, filter_dict: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve parts matching filter attributes."""
        pass


class InMemoryPartRepo(BasePartRepo):
    """
    In-memory implementation of BasePartRepo for offline unit tests.
    Initialized with a list or dictionary of component records.
    """

    def __init__(self, parts: Optional[List[Dict[str, Any]]] = None):
        self._parts: Dict[str, Dict[str, Any]] = {}
        if parts:
            for p in parts:
                pid = str(p.get("_id") or p.get("id", "")).strip()
                if pid:
                    record = dict(p)
                    record["id"] = pid
                    record["_id"] = pid
                    self._parts[pid] = record

    def add_part(self, part: Dict[str, Any]) -> None:
        """Helper to seed test data into in-memory repo."""
        pid = str(part.get("_id") or part.get("id", "")).strip()
        if pid:
            record = dict(part)
            record["id"] = pid
            record["_id"] = pid
            self._parts[pid] = record

    def get_one(self, part_id: str) -> Optional[Dict[str, Any]]:
        pid = str(part_id).strip()
        doc = self._parts.get(pid)
        return dict(doc) if doc else None

    def get_many(self, part_ids: List[str]) -> List[Dict[str, Any]]:
        result = []
        for pid in part_ids:
            doc = self.get_one(pid)
            if doc:
                result.append(doc)
        return result

    def get_all(self) -> List[Dict[str, Any]]:
        return [dict(doc) for doc in self._parts.values()]

    def get_by_filter(self, filter_dict: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        matched = []
        for doc in self._parts.values():
            match = True
            for k, v in filter_dict.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                matched.append(dict(doc))
                if len(matched) >= limit:
                    break
        return matched


class MongoPartRepo(BasePartRepo):
    """
    MongoDB implementation of BasePartRepo.
    Wraps 'catalog_parts' collection with read-only methods.
    """

    def __init__(self, uri: Optional[str] = None, db_name: Optional[str] = None):
        from pymongo import MongoClient

        self.uri = uri or MONGODB_URI
        # Extract db name from URI or default to "PC"
        if not db_name:
            if "/" in self.uri.split("?")[0]:
                inferred = self.uri.split("?")[0].rstrip("/").split("/")[-1]
                self.db_name = inferred if inferred and not inferred.startswith("mongodb") else "PC"
            else:
                self.db_name = "PC"
        else:
            self.db_name = db_name

        self._client = MongoClient(self.uri, serverSelectionTimeoutMS=2000)
        self._db = self._client[self.db_name]
        self._collection = self._db["catalog_parts"]

    def get_one(self, part_id: str) -> Optional[Dict[str, Any]]:
        pid = str(part_id).strip()
        doc = self._collection.find_one({"_id": pid})
        if not doc:
            # Fallback for case variations
            doc = self._collection.find_one({"_id": pid.lower()})
        if doc:
            doc["id"] = str(doc["_id"])
            if "price" not in doc and "price_inr" in doc:
                doc["price"] = doc["price_inr"]
        return doc

    def get_many(self, part_ids: List[str]) -> List[Dict[str, Any]]:
        clean_ids = [str(pid).strip() for pid in part_ids]
        cursor = self._collection.find({"_id": {"$in": clean_ids}})
        found_map: Dict[str, Dict[str, Any]] = {}
        for doc in cursor:
            doc_id = str(doc["_id"])
            doc["id"] = doc_id
            if "price" not in doc and "price_inr" in doc:
                doc["price"] = doc["price_inr"]
            found_map[doc_id] = doc

        # Return list preserving or matching found items
        return list(found_map.values())

    def get_all(self) -> List[Dict[str, Any]]:
        cursor = self._collection.find({})
        results = []
        for doc in cursor:
            doc["id"] = str(doc["_id"])
            if "price" not in doc and "price_inr" in doc:
                doc["price"] = doc["price_inr"]
            results.append(doc)
        return results

    def get_by_filter(self, filter_dict: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self._collection.find(filter_dict).limit(limit)
        results = []
        for doc in cursor:
            doc["id"] = str(doc["_id"])
            if "price" not in doc and "price_inr" in doc:
                doc["price"] = doc["price_inr"]
            results.append(doc)
        return results


def get_repo(in_memory_data: Optional[List[Dict[str, Any]]] = None) -> BasePartRepo:
    """
    Factory function: returns InMemoryPartRepo if data is supplied,
    otherwise connects to MongoPartRepo.
    """
    if in_memory_data is not None:
        return InMemoryPartRepo(parts=in_memory_data)
    try:
        repo = MongoPartRepo()
        # Verify connection
        repo._client.admin.command("ping")
        return repo
    except Exception:
        # Fallback to empty in-memory repo if Mongo is unavailable
        return InMemoryPartRepo()
