import re
from compat import ALL_SPECS


def extract_budget(text: str) -> float | None:
    """Extract budget number from user text via regex (e.g. 75000, 75k, 60,000, 1 lakh)."""
    if not text:
        return None

    # If full architect prompt was passed, only inspect the user request section
    if "User request:" in text:
        text = text.split("User request:")[-1]

    # Check for lakh (e.g. "1 lakh", "1.5 lakh", "2 lakhs", "1 lac")
    lakh_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakh|lac)s?\b', text, re.IGNORECASE)
    if lakh_match:
        try:
            return float(lakh_match.group(1)) * 100000.0
        except ValueError:
            pass

    # Check for "k" notation (e.g. "75k", "50 k", "100k")
    k_match = re.search(r'\b(\d+(?:\.\d+)?)\s*k\b', text, re.IGNORECASE)
    if k_match:
        try:
            return float(k_match.group(1)) * 1000.0
        except ValueError:
            pass

    # Check for 4-7 digit numbers, optionally with commas (e.g. "75,000", "75000", "105000")
    nums = re.findall(
        r'(?:rs\.?|inr|₹|under|budget|for|around)?\s*(\d{1,3}(?:,\d{3})+|\d{4,7})\b',
        text,
        re.IGNORECASE,
    )
    for n in nums:
        clean = n.replace(',', '')
        try:
            val = float(clean)
            if 1000 <= val <= 2000000:
                return val
        except ValueError:
            continue

    return None


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
