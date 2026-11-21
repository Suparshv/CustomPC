"""
budget.py - Splits the user's budget across the 9 part categories.

Code, not the AI, decides how much each part may cost. In the 8 Nov baseline the
most common failure was going over budget (4 of 6 invalid builds), so each pick
gets a price cap.

Carry-forward: each category gets its share of the money that is STILL LEFT,
divided among the categories still to pick. If the CPU costs less than its share,
the saving flows to the later parts automatically.
"""

from typing import Iterable, Optional

# The order parts are picked in. Later picks are filtered by earlier ones:
# board by CPU socket, RAM by board, PSU by CPU+GPU power, case by board size.
PICK_ORDER = ["processor", "motherboard", "ram", "gpu", "psu", "cabinet", "cooling", "ps", "ss"]

# Typical gaming-PC split. Must add up to 1.0.
BUDGET_SHARES = {
    "gpu": 0.35,
    "processor": 0.17,
    "motherboard": 0.12,
    "ram": 0.08,
    "ps": 0.07,          # primary SSD
    "psu": 0.07,
    "cabinet": 0.06,
    "cooling": 0.04,
    "ss": 0.04,          # secondary storage
}


def category_cap(category: str, budget: Optional[float], spent: float, picked: Iterable[str]) -> Optional[float]:
    """
    Maximum price for the next `category`, or None when the user gave no budget.

    cap = money left * (this category's share / shares of all categories not picked yet)
    """
    if budget is None:
        return None
    left = max(0.0, float(budget) - float(spent))
    picked = set(picked)
    still_to_pick = [c for c in PICK_ORDER if c not in picked]
    shares_left = sum(BUDGET_SHARES[c] for c in still_to_pick)
    if category not in still_to_pick or shares_left <= 0:
        return left
    return left * BUDGET_SHARES[category] / shares_left
