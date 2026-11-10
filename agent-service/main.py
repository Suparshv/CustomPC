from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ValidationError
from compat import ALL_SPECS
from llm import get_llm, LLMError
from schemas import DraftBuild

app = FastAPI(title="PC Builder agent service")

# Lazy LLM loader so importing main.py does not crash if GEMINI_API_KEY is not set yet
_llm = None


def get_current_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


ARCHITECT_SYSTEM = """You are the Architect Agent for a custom PC store.
Your job is to draft a PC build based ONLY on the provided relevant parts.

CRITICAL RULES:
1. Do not hallucinate parts. Only use the IDs in the AVAILABLE PARTS list.
2. If the user asks for a FULL PC build, you MUST include exactly 1 component from EACH of the 9 categories: processor, motherboard, gpu, ram, ps, ss, psu, cabinet, and cooling. ('ps' is Primary Storage, 'ss' is Secondary Storage). Do not skip any! If they only want parts, only output those.
3. ENSURE HARDWARE COMPATIBILITY: Do NOT bottleneck a high-end GPU with a weak CPU. Ensure the Motherboard socket matches the CPU socket. Ensure Motherboard RAM type matches the RAM. 
4. Do NOT use any emojis or markdown formatting.
5. Keep your "reply" extremely brief and concise. Maximum 3 sentences."""


# NOTE: The debug route is for local development only. Added length limit to prevent unbounded token spending.
class Ask(BaseModel):
    message: str = Field(min_length=1, max_length=500, description="User request (max 500 characters)")


@app.get("/health")
def health():
    try:
        llm = get_current_llm()
        return {
            "status": "ok",
            "provider": llm.provider,
            "model": getattr(llm, "model", None),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@app.post("/debug/draft-build")
def draft_build(ask: Ask):
    try:
        llm = get_current_llm()
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
    except ValidationError as e:
        # LLM output did not match Pydantic schema or failed a validator
        raise HTTPException(
            status_code=422,
            detail={"error": "ValidationError", "message": "AI answer failed schema validation", "details": e.errors()},
        )
    except LLMError as e:
        # LLM provider error (e.g. blocked, empty text)
        raise HTTPException(
            status_code=502,
            detail={"error": "LLMError", "message": str(e)},
        )
    except NotImplementedError as e:
        raise HTTPException(
            status_code=501,
            detail={"error": "NotImplementedError", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": type(e).__name__, "message": str(e)},
        )
