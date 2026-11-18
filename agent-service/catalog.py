import re
from compat import ALL_SPECS


# ─── Budget extraction ────────────────────────────────────────────────────────
_BUDGET_NUMBER_RE = re.compile(
    r"(?<!\w)(?<!\w-)(?<!\d\.)"
    r"(?P<num>\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?)"
    r"(?:\s?(?P<suffix>lakhs?|lacs?|l|k))?"
    r"(?![\w])",
    re.IGNORECASE,
)

_MONEY_BEFORE_RE = re.compile(r"(?:₹|\brs\.?|\binr)\s*$", re.IGNORECASE)
_MONEY_AFTER_RE = re.compile(r"^\s*(?:₹|rupees?\b|rs\b|inr\b|/-)", re.IGNORECASE)

# "for" is weak: "for 4K gaming" is not money, so it is kept out of the strong list.
_STRONG_BUDGET_WORDS = r"budget|under|below|within|max|maximum|upto|up\s+to|around|about|less\s+than|approx(?:imately)?"
_BUDGET_WORD_BEFORE_RE = re.compile(
    r"\b(?P<word>" + _STRONG_BUDGET_WORDS + r"|for)"
    r"\s*(?:is|of|:|=)?\s*(?:around|about|approx(?:imately)?|roughly)?\s*(?:₹|rs\.?|inr)?\s*$",
    re.IGNORECASE,
)
_BUDGET_WORD_AFTER_RE = re.compile(r"^\s*(?:budget|max)\b", re.IGNORECASE)


def _budget_from_match(text: str, m: re.Match) -> float | None:
    """Return the rupee amount for one number match, or None if it is not money."""
    raw = m.group("num")
    value = float(raw.replace(",", ""))
    suffix = (m.group("suffix") or "").lower()
    before, after = text[: m.start()], text[m.end():]

    has_money_marker = bool(_MONEY_BEFORE_RE.search(before) or _MONEY_AFTER_RE.search(after))
    word = _BUDGET_WORD_BEFORE_RE.search(before)
    strong_word = bool(word and word.group("word").lower() != "for") or bool(_BUDGET_WORD_AFTER_RE.search(after))
    any_word = bool(word) or strong_word

    if suffix.startswith("la") or suffix == "l":
        return value * 100_000
    if suffix == "k":
        # "4K"/"8K" with nothing saying "money" is a screen resolution, not Rs.4000.
        if value < 10 and not (has_money_marker or strong_word):
            return None
        return value * 1_000
    if has_money_marker:
        return value
    if "," in raw:
        return value
    # A bare number needs a budget word, and must be a plausible amount: "for 2 monitors" is not Rs.2.
    if any_word and value >= 1000:
        return value
    return None


def extract_budget(text: str) -> float | None:
    """
    Extract the user's budget in rupees from their own words, or None if they gave none.

    Examples: "80k" -> 80000, "1.5 lakh" -> 150000, "₹1,20,000" -> 120000,
    "RTX 4060 build under 80000" -> 80000, "4K gaming PC" -> None.
    If several amounts are written, the largest is the budget ("under 80k, ideally 70k").
    """
    if not text:
        return None

    # Safety net: if the full architect prompt was passed, only read the user's part.
    # The parts list above it is full of prices ("Rs.10500") that are NOT the budget.
    # Callers should pass the raw request (llm.generate's budget_source) anyway.
    if "User request:" in text:
        text = text.split("User request:")[-1]

    amounts = [a for a in (_budget_from_match(text, m) for m in _BUDGET_NUMBER_RE.finditer(text)) if a]
    return float(max(amounts)) if amounts else None


def check_build(draft) -> list[str]:
    problems = []

    # 1. Finding A: Make empty answers fail the check
    if not draft.build:
        problems.append("build is empty, list every recommended part as {category, id} in build")

    # 2. Check each item in draft.build
    build_ids = set()
    for item in draft.build:
        spec = ALL_SPECS.get(item.id)
        if spec is None:
            problems.append(f"part id '{item.id}' does not exist in AVAILABLE PARTS")
        elif spec["category"] != item.category:
            problems.append(f"part '{item.id}' is a {spec['category']}, not a {item.category}")
        build_ids.add(item.id.strip().lower())

    # 3. Finding A: Catch IDs hidden in the reply text but missing from build list
    reply_tokens = set(re.findall(r'\b[a-z0-9]+\b', draft.reply.lower()))
    for spec_id in ALL_SPECS.keys():
        if spec_id.lower() in reply_tokens and spec_id.lower() not in build_ids:
            problems.append(f"part id '{spec_id}' was mentioned in reply but missing from build list")

    return problems
