"""
tool_models.py - Pydantic models for Day 8 Tool Inputs and Outputs

Provides strict schema validation, bounds checking, and input sanitization
for search_parts, price_total, and check_compatibility tools.
Ensures tool calls fail cleanly with descriptive error messages rather than crashing.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator

from normalize import normalize_category, normalize_socket, normalize_ram_type, normalize_form_factor


ALLOWED_CATEGORIES = {
    "processor", "cpu", "motherboard", "mobo", "gpu", "video_card", "videocard",
    "ram", "memory", "storage", "ps", "ssd", "ss", "hdd",
    "psu", "power_supply", "cabinet", "case", "cooling", "cooler", "os"
}


class SearchPartsInput(BaseModel):
    """Input parameters for search_parts tool."""
    category: str = Field(
        ...,
        description="Hardware component category (e.g. 'processor', 'motherboard', 'gpu', 'ram', 'psu', 'cabinet', 'cooling', 'storage', 'os').",
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
    cooler_kind: Optional[str] = Field(
        default=None,
        description="Cooling type: 'air' or 'liquid'.",
    )
    limit: int = Field(
        default=8,
        description="Number of candidate parts to return (default 8, minimum 1, maximum 10).",
    )

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("category is required and cannot be empty.")
        clean = str(v).strip().lower()
        norm = normalize_category(clean)
        if not norm or (clean not in ALLOWED_CATEGORIES and norm not in ALLOWED_CATEGORIES):
            valid_list = ", ".join(sorted(list(set(ALLOWED_CATEGORIES))))
            raise ValueError(f"Invalid category '{v}'. Allowed categories are: {valid_list}")
        return norm

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

    @field_validator("cooler_kind")
    @classmethod
    def validate_cooler_kind(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = str(v).strip().lower()
            if clean not in ("air", "liquid"):
                raise ValueError("cooler_kind must be either 'air' or 'liquid'.")
            return clean
        return None

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
    wattage: Optional[float] = None
    length_mm: Optional[float] = None
    height_mm: Optional[float] = None
    cooler_kind: Optional[str] = None
    in_stock: bool = True
    checkable: bool = False
