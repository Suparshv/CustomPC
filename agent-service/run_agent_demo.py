#!/usr/bin/env python3
"""
run_agent_demo.py - Day 10 real run: one request through the agent on Gemini and/or Ollama.

Needs MongoDB, the Chroma Docker server and Ollama (for search embeddings, and for the
Ollama run), plus GEMINI_API_KEY for the Gemini run. Writes docs/day10-agent-run.md.

    python run_agent_demo.py "Gaming PC under 75000"
    python run_agent_demo.py "Gaming PC under 75000" --providers ollama
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agent_config import AgentConfig  # noqa: E402
from agent_graph import CATEGORY_LABELS, run_agent, warm_up  # noqa: E402
from budget import PICK_ORDER  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "day10-agent-run.md"


def require_chroma_server() -> None:
    """Refuse to run on the local fallback copy: it may be an old index (CHROMA_ALLOW_FALLBACK)."""
    import chromadb
    from build_index import CHROMA_HOST, CHROMA_PORT
    try:
        chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT).heartbeat()
    except Exception:
        sys.exit(f"Chroma server at {CHROMA_HOST}:{CHROMA_PORT} is not running. Start it "
                 f"(e.g. 'docker start chroma'). Not using the local fallback copy: it may be out of date.")


def make_llm(provider: str):
    from llm import GeminiLLM, OllamaLLM
    return GeminiLLM() if provider == "gemini" else OllamaLLM()


def to_markdown(res: dict, provider: str, model: str) -> str:
    lines = [
        f"## {provider} (`{model}`)",
        "",
        f"- **Status:** `{res['status']}` | route `{res['route']}` | budget read by code: "
        f"{('₹{:,}'.format(int(res['budget']))) if res['budget'] else 'none'}",
        f"- **AI pick steps:** {res['steps']} | **repairs:** {res['repairs']} | "
        f"**time:** {res['seconds']} s | **tokens:** {res['tokens'].get('prompt', 0)} in / "
        f"{res['tokens'].get('output', 0)} out",
        f"- **Switches:** `{json.dumps(res['config'])}`",
        "",
        "| Step | Category | Chosen | Price | From N candidates | AI's reason |",
        "|---|---|---|---|---|---|",
    ]
    n = 0
    for e in res["history"]:
        if e["step"] == "pick":
            n += 1
            card = res["picks"].get(e["category"], {})
            name = card.get("name", e["chosen"]) if card.get("id") == e["chosen"] else e["chosen"]
            price = card.get("price") if card.get("id") == e["chosen"] else None
            lines.append(f"| {n} | {CATEGORY_LABELS[e['category']]} | {name} | "
                         f"{'₹{:,}'.format(int(price)) if price else '(replaced later)'} | "
                         f"{len(e['candidates'])} | {e['reason']} |")
        elif e["step"] == "repair":
            lines.append(f"| repair {e['round']} | {', '.join(e['repick'])} | failed: {', '.join(e['failed_rules'])} | | | |")
        elif e["step"] == "one_shot":
            lines.append("| 1 | all | one AI call (tools off) | | | |")
    every_id_from_search = all(e["chosen"] in e["candidates"] for e in res["history"] if e["step"] == "pick")
    lines += ["", f"Every chosen ID came from a search result: **{every_id_from_search}**", ""]
    if res.get("check"):
        lines += ["| Rule | Verdict | Message |", "|---|---|---|"]
        for rule, r in res["check"]["rules"].items():
            lines.append(f"| {rule} | {r['verdict']} | {r['message']} |")
        lines.append("")
    lines += ["**Reply shown to the user:**", "", "```text", res["reply"], "```", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("request", nargs="?", default="Gaming PC under 75000")
    ap.add_argument("--providers", nargs="+", default=["gemini", "ollama"], choices=["gemini", "ollama"])
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()

    require_chroma_server()
    cfg = AgentConfig.from_env()
    # Same as the API service at start-up: pay the one-time loads BEFORE timing any request.
    print("Warm-up:", warm_up(cfg))
    parts = [f"# Day 10 agent run\n\n> Request: **\"{args.request}\"** - run "
             f"{datetime.datetime.now():%Y-%m-%d %H:%M}. Measured, single run per provider.\n"]
    for provider in args.providers:
        llm = make_llm(provider)
        print(f"Running on {provider} ({llm.model})...")
        res = run_agent(args.request, llm, cfg)
        print(f"  -> {res['status']} in {res['seconds']} s, {res['steps']} picks, {res['repairs']} repairs")
        print(res["reply"], "\n")
        parts.append(to_markdown(res, provider, llm.model))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(parts), encoding="utf-8")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
