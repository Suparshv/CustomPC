"""
tool_models.py - Pydantic models for tool inputs and outputs

Provides strict schema validation, bounds checking, and input sanitization
for search_parts, price_total, and check_compatibility tools.
Ensures tool calls fail cleanly with descriptive error messages rather than crashing.
"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator

from normalize import (
    normalize_category,
    normalize_form_factor,
    normalize_ram_type,
    normalize_socket,
)

# Canonical 9 categories in the catalogue plus developer-friendly aliases (excluding 'os')
CategoryLiteral = Literal[
    "processor",
    "motherboard",
    "gpu",
    "ram",
    "ps",
    "ss",
    "psu",
    "cabinet",
    "cooling",
    "cpu",
    "mobo",
    "case",
    "cooler",
]


class SearchPartsInput(BaseModel):
    """Input parameters for search_parts tool."""
    category: CategoryLiteral = Field(
        ...,
        description="Hardware component category: 'processor', 'motherboard', 'gpu', 'ram', 'ps' (SSD), 'ss' (HDD), 'psu', 'cabinet', 'cooling'.",
    )
    keywords: Optional[str] = Field(
        default="",
        description="Search keywords or descriptive requirements (e.g. 'quiet 1440p gaming', 'white aesthetics', 'Corsair'). Max 200 chars.",
    )
    max_price: Optional[float] = Field(
        default=None,
        description="Maximum price budget for this component in INR (must be positive).",
    )
    in_stock_only: bool = Field(
        default=True,
        description="If True, only return parts currently marked in-stock.",
    )
    socket: Optional[str] = Field(
        default=None,
        description="Target CPU/Motherboard socket (e.g. 'AM5', 'AM4', 'LGA1700', 'LGA1851').",
    )
    ram_type: Optional[str] = Field(
        default=None,
        description="RAM generation ('DDR4' or 'DDR5').",
    )
    allowed_form_factors: Optional[List[str]] = Field(
        default=None,
        description="Allowed form factors (e.g. ['ATX', 'Micro ATX', 'Mini ITX']).",
    )
    min_wattage: Optional[float] = Field(
        default=None,
        description="Minimum power supply wattage in Watts (must be positive).",
    )
    max_gpu_length: Optional[float] = Field(
        default=None,
        description="Maximum physical length of GPU in mm (must be positive).",
    )
    cooler_kind: Optional[Literal["air", "liquid"]] = Field(
        default=None,
        description="Cooling type: 'air' or 'liquid'.",
    )
    retriever: Literal["vector", "hybrid", "hybrid_rerank"] = Field(
        default="vector",
        description="Retrieval strategy: 'vector' (Chroma vector search), 'hybrid' (vector + BM25 keyword merged via RRF), or 'hybrid_rerank' (hybrid + CrossEncoder reranker).",
    )
    limit: int = Field(
        default=8,
        description="Number of candidate parts to return (default 8, minimum 1, maximum 10).",
    )

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        clean = str(v).strip().lower()
        norm = normalize_category(clean)
        return norm or clean

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v: Optional[str]) -> str:
        if v is None:
            return ""
        s = str(v).strip()
        if len(s) > 200:
            raise ValueError(f"keywords capped at 200 characters (got {len(s)} characters).")
        return s

    @field_validator("max_price")
    @classmethod
    def validate_max_price(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("max_price must be positive.")
        return v

    @field_validator("socket")
    @classmethod
    def validate_socket(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return normalize_socket(v)
        return None

    @field_validator("ram_type")
    @classmethod
    def validate_ram_type(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return normalize_ram_type(v)
        return None

    @field_validator("allowed_form_factors")
    @classmethod
    def validate_allowed_form_factors(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v:
            clean = [normalize_form_factor(x) for x in v if x]
            return [x for x in clean if x]
        return None

    @field_validator("min_wattage")
    @classmethod
    def validate_min_wattage(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("min_wattage must be positive.")
        return v

    @field_validator("max_gpu_length")
    @classmethod
    def validate_max_gpu_length(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("max_gpu_length must be positive.")
        return v

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError(f"limit must be between 1 and 10 (got {v}).")
        return v


class PriceTotalInput(BaseModel):
    """Input parameters for price_total tool."""
    part_ids: List[str] = Field(
        ...,
        description="List of component IDs to price (repeated IDs are counted multiple times).",
    )


class CheckCompatibilityInput(BaseModel):
    """Input parameters for check_compatibility tool."""
    part_ids: List[str] = Field(
        ...,
        description="List of component IDs representing the complete or partial build to verify.",
    )
    budget: Optional[float] = Field(
        default=None,
        description="Optional maximum budget threshold in INR to test against total build price.",
    )
    partial: bool = Field(
        default=False,
        description=(
            "True while the build is still being assembled: categories not chosen yet are "
            "reported as UNKNOWN instead of FAIL. Use false (default) for the final check."
        ),
    )

    @field_validator("budget")
    @classmethod
    def validate_budget(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("budget must be positive.")
        return v


class PartCard(BaseModel):
    """Compact representation of a hardware component returned to the agent."""
    id: str
    name: str
    category: str
    price: Optional[float] = None
    socket: Optional[str] = None
    ram_type: Optional[str] = None
    form_factor: Optional[str] = None
    case_type: Optional[str] = None
    wattage: Optional[float] = None
    tdp: Optional[float] = None  # CPU/GPU power draw in W; the agent needs it for PSU sizing
    length_mm: Optional[float] = None
    height_mm: Optional[float] = None
    cooler_kind: Optional[str] = None
    radiator_size: Optional[int] = None
    gpu_memory: Optional[int] = None
    speed_mhz: Optional[int] = None
    capacity_gb: Optional[int] = None
    in_stock: bool = True
    checkable: bool = False
