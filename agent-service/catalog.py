from compat import ALL_SPECS


def check_build(draft) -> list[str]:
    problems = []
    for item in draft.build:
        spec = ALL_SPECS.get(item.id)
        if spec is None:
            problems.append(f"part id '{item.id}' does not exist in AVAILABLE PARTS")
        elif spec["category"] != item.category:
            problems.append(f"part '{item.id}' is a {spec['category']}, not a {item.category}")
    return problems
