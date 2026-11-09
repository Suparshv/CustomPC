from fastapi import FastAPI
from pydantic import BaseModel
from compat import ALL_SPECS
from llm import get_llm
from schemas import DraftBuild

app = FastAPI(title="PC Builder agent service")
llm = get_llm()

ARCHITECT_SYSTEM = """You are the Architect Agent for a custom PC store.
Your job is to draft a PC build based ONLY on the provided relevant parts.

CRITICAL RULES:
1. Do not hallucinate parts. Only use the IDs provided above.
2. If the user asks for a FULL PC build, you MUST include exactly 1 component from EACH of the 9 categories: processor, motherboard, gpu, ram, ps, ss, psu, cabinet, and cooling. ('ps' is Primary Storage, 'ss' is Secondary Storage). Do not skip any! If they only want parts, only output those.
3. ENSURE HARDWARE COMPATIBILITY: Do NOT bottleneck a high-end GPU with a weak CPU. Ensure the Motherboard socket matches the CPU socket. Ensure Motherboard RAM type matches the RAM. 
4. Do NOT use any emojis or markdown formatting.
5. Keep your "reply" extremely brief and concise. Maximum 3 sentences."""


class Ask(BaseModel):
    message: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": llm.provider,
        "model": getattr(llm, "model", None),
    }


@app.post("/debug/draft-build")
def draft_build(ask: Ask):
    parts = "\n".join(
        f"{k} | {v['category']} | {v['name']} | Rs.{v['price']}"
        for k, v in ALL_SPECS.items()
    )
    r = llm.generate(
        ARCHITECT_SYSTEM,
        f"AVAILABLE PARTS:\n{parts}\n\nUser request: {ask.message}",
        DraftBuild,
    )
    return {
        "result": r.parsed,
        "provider": r.provider,
        "model": r.model,
        "tokens": r.prompt_tokens + r.output_tokens,
        "seconds": r.seconds,
    }
