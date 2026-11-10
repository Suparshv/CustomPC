from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from llm import get_llm, LLMError, LLMValidationError
from schemas import DraftBuild
from catalog import check_build
from prompts import ARCHITECT_SYSTEM, format_architect_user_prompt

app = FastAPI(title="PC Builder agent service")

# Lazy LLM loader so importing main.py does not crash if API keys/environment are missing
_llm = None


def get_current_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


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
        user_prompt = format_architect_user_prompt(ask.message)
        r = llm.generate(
            ARCHITECT_SYSTEM,
            user_prompt,
            DraftBuild,
            check=check_build,
        )
        return {
            "result": r.parsed,
            "provider": r.provider,
            "model": r.model,
            "tokens": r.prompt_tokens + r.output_tokens,
            "seconds": r.seconds,
            "attempts": r.attempts,
        }
    except LLMValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "LLMValidationError",
                "problems": e.problems,
                "attempts": e.attempts,
            },
        )
    except LLMError as e:
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
