"""Marketing Content Generator API (FastAPI).

Endpoints
  GET  /health       liveness + which backend is active (openai:<model>, anthropic:<model> or demo)
  GET  /options      campaign types, platforms, tones and languages for clients
  POST /generate     first draft from a brief
  POST /refine       revise the current draft with feedback
  POST /translate    translate the current draft
  POST /variants     2–3 A/B test variants of the brief, each from a different angle
Interactive docs at /docs (OpenAPI).

Protection for a public deployment (all configurable, see .env.example):
  APP_API_KEY        if set, requests need the header  X-API-Key: <value>
  RATE_LIMIT_PER_MIN requests per client IP per minute (default 20)
  CORS_ORIGINS       comma-separated allowed origins (default: none; the Streamlit UI calls server-side)
Input sizes are capped by the request models.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import service
from .campaigns import CAMPAIGNS, CHAR_LIMITS, LANGUAGES, TONES
from .llm import LLM, env, env_number, from_env

log = logging.getLogger("marketing-api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="Marketing Content Generator API",
    version="2.0.0",
    description="Generate, refine and translate marketing copy with an LLM.",
)
origins = [o.strip() for o in env("CORS_ORIGINS").split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

_llm: Optional[LLM] = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = from_env()
        log.info("LLM backend: %s", _llm.name)
    return _llm


# ─── protection ───────────────────────────────────────────────────────────────
_hits: Dict[str, Deque[float]] = defaultdict(deque)


def guard(request: Request) -> None:
    key = env("APP_API_KEY")
    if key and request.headers.get("x-api-key") != key:
        raise HTTPException(401, "Missing or invalid X-API-Key header.")
    limit = max(1, int(env_number("RATE_LIMIT_PER_MIN", 20)))
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    now, window = time.monotonic(), _hits[ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(429, f"Rate limit reached ({limit} requests per minute). Try again shortly.")
    window.append(now)


# ─── request models ───────────────────────────────────────────────────────────
class Brief(BaseModel):
    campaign_type: str = Field(..., examples=["social_media"])
    tone: str = Field("professional", max_length=40, examples=["friendly"])
    topic: str = Field(..., min_length=3, max_length=1500, examples=["our new budgeting app for students"])
    audience: Optional[str] = Field(None, max_length=300, examples=["university students"])
    platform: Optional[str] = Field(None, max_length=40, examples=["LinkedIn"])
    language: str = Field("English", max_length=30)
    extra_instructions: Optional[str] = Field(None, max_length=1000)


class RefineRequest(Brief):
    draft: str = Field(..., min_length=1, max_length=8000)
    feedback: str = Field(..., min_length=2, max_length=1000, examples=["shorter, and mention the free trial"])


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    language: str = Field(..., max_length=30, examples=["German"])
    platform: Optional[str] = Field(None, max_length=40)


class VariantsRequest(Brief):
    count: int = Field(3, ge=2, le=3, description="How many A/B variants (2–3), each from a different angle")


class Copy(BaseModel):
    content: str
    backend: str


class Variant(BaseModel):
    angle: str
    content: str


class Variants(BaseModel):
    variants: List[Variant]
    backend: str


def _call(fn, **kwargs):
    llm = get_llm()
    try:
        return fn(llm, **kwargs), llm.name
    except ValueError as e:  # invalid campaign/platform combination
        raise HTTPException(422, str(e)) from e
    except Exception as e:  # upstream/model failure: log it, don't leak it
        log.exception("LLM call failed")
        raise HTTPException(502, _failure_message(e)) from e


# the provider's HTTP status says what went wrong without exposing its message (which may echo input)
_FAILURES = {
    400: "the provider rejected the request — check the API key and model name",
    401: "the API key was rejected — check it in the deployment settings",
    403: "the API key has no access to this model or region",
    404: "the model was not found — check the model name",
    429: "the provider's rate limit or free quota is used up — try again later",
}


def _failure_message(e: Exception) -> str:
    status = getattr(e, "status_code", None)
    reason = _FAILURES.get(status) if isinstance(status, int) else None
    if reason is None and isinstance(status, int) and status >= 500:
        reason = "the model provider is having problems"
    # which request field the provider objected to (a field name, never the provider's free text)
    body = getattr(e, "body", None)
    param = body.get("param") if isinstance(body, dict) else None
    if isinstance(param, str) and param.replace("_", "").isalnum() and len(param) <= 40:
        reason = f"{reason}; the provider objected to '{param}'" if reason else None
    if reason:
        return f"The language model could not produce copy ({status}: {reason})."
    return "The language model could not produce copy right now. Please retry."


def _run(fn, **kwargs) -> Copy:
    content, backend = _call(fn, **kwargs)
    return Copy(content=content, backend=backend)


# ─── routes ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health() -> dict:
    return {"status": "ok", "backend": get_llm().name}


@app.get("/options")
def options() -> dict:
    return {
        "campaigns": {k: {"label": c.label, "platforms": list(c.platforms)} for k, c in CAMPAIGNS.items()},
        "tones": list(TONES),
        "languages": list(LANGUAGES),
        "char_limits": CHAR_LIMITS,
    }


@app.post("/generate", response_model=Copy, dependencies=[Depends(guard)])
def generate(req: Brief) -> Copy:
    return _run(service.generate, **req.model_dump())


@app.post("/variants", response_model=Variants, dependencies=[Depends(guard)])
def make_variants(req: VariantsRequest) -> Variants:
    items, backend = _call(service.variants, **req.model_dump())
    return Variants(variants=[Variant(**v) for v in items], backend=backend)


@app.post("/refine", response_model=Copy, dependencies=[Depends(guard)])
def refine(req: RefineRequest) -> Copy:
    return _run(service.refine, **req.model_dump())


@app.post("/translate", response_model=Copy, dependencies=[Depends(guard)])
def translate(req: TranslateRequest) -> Copy:
    return _run(service.translate, **req.model_dump())
