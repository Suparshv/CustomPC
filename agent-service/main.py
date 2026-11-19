import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import httpx
from google.genai import errors

import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from agent_config import AgentConfig
from agent_graph import run_agent, warm_up
from llm import get_llm, LLMError, LLMValidationError
from schemas import DraftBuild
from catalog import check_build
from prompts import ARCHITECT_SYSTEM, format_architect_user_prompt

logger = logging.getLogger("agent-service")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load the slow parts (Chroma, Ollama embedding model, keyword index, reranker) once at
    # start-up, so no user request pays the 9-33 s cold start. AGENT_WARMUP=0 turns it off.
    if os.getenv("AGENT_WARMUP", "1").strip().lower() not in ("0", "false", "no", "off"):
        try:
            llm = get_current_llm()          # Ollama: its chat model gets loaded too
        except Exception as e:               # e.g. no API key: the requests will report it
            logger.warning("Warm-up: LLM not available (%s)", e)
            llm = None
        logger.info("Warm-up: %s", warm_up(AgentConfig.from_env(), llm=llm))
    yield


app = FastAPI(title="PC Builder agent service", lifespan=lifespan)

# Lazy LLM loader so importing main.py does not crash if API keys/environment are missing
_llm = None


def get_current_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


class Ask(BaseModel):
    message: str = Field(min_length=1, max_length=500, description="User request (max 500 characters)")


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500, description="User request (max 500 characters)")
    overrides: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Switches for this request only, e.g. {\"use_checker\": false, \"repair_loops\": 0}",
    )


@app.post("/agent/build")
def agent_build(req: AgentRequest):
    """
    Run the Day 10 agent on one request.
    200: the agent answered (valid, no_valid_build, unverified, refused, comparison, step_limit...).
    422: bad request or bad switch values.  503: the AI or a data service is unavailable.
    """
    try:
        config = AgentConfig.from_env().with_overrides(req.overrides)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=422, detail={"error": "InvalidSwitches", "message": str(e)})
    try:
        llm = get_current_llm()
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "error": f"LLM not available: {e}"})

    result = run_agent(req.message, llm, config)   # never raises: failures come back as status "error"
    # Say which AI produced the answer, so eval reports describe the system that actually ran.
    result["provider"] = getattr(llm, "provider", None)
    result["model"] = getattr(llm, "model", None)
    if result.get("status") == "error":
        return JSONResponse(status_code=503, content=result)
    return result


@app.get("/health")
def health():
    # Finding E: Clean single Exception handler covering all connection/readiness errors
    try:
        llm = get_current_llm()
        health_info = llm.check_health()
        return health_info
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "provider": getattr(_llm, "provider", "unknown") if _llm else "unknown",
                "error": str(e),
            },
        )


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
            budget_source=ask.message,  # read the budget from the request only, not the price list
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
    except errors.APIError as e:
        # Finding B: Map Google API 503/429 to HTTP 503 with retry-after hint
        if getattr(e, "code", None) in (503, 429):
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "ServiceUnavailable",
                    "message": f"Gemini API is temporarily overloaded ({e.code}). Please retry.",
                    "code": e.code,
                },
                headers={"Retry-After": "5"},
            )
        raise HTTPException(
            status_code=502,
            detail={"error": "LLMProviderError", "message": str(e)},
        )
    except (httpx.ConnectError, httpx.ConnectTimeout, ConnectionError) as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "ServiceUnavailable", "message": f"Cannot connect to LLM provider: {str(e)}"},
        )
    except LLMError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "LLMError", "message": str(e)},
        )
    except Exception as e:
        # Finding C: Log unexpected errors so server logs preserve stack traces
        logger.exception("Unexpected error in draft_build: %s", e)
        raise HTTPException(
            status_code=500,
            detail={"error": "InternalServerError", "message": "An unexpected server error occurred."},
        )
