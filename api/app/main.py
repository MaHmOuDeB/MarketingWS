"""Marketing Content Generator API (FastAPI).

Endpoints
  GET  /health       liveness + which backend is active (openai:<model> or demo)
  GET  /options      campaign types, platforms, tones and languages for clients
  POST /generate     first draft from a brief
  POST /refine       revise the current draft with feedback
  POST /translate    translate the current draft
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
from typing import Deque, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import service
from .campaigns import CAMPAIGNS, LANGUAGES, TONES
from .llm import LLM, from_env

log = logging.getLogger("marketing-api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="Marketing Content Generator API",
    version="2.0.0",
    description="Generate, refine and translate marketing copy with an LLM.",
)
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
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
    key = os.getenv("APP_API_KEY")
    if key and request.headers.get("x-api-key") != key:
        raise HTTPException(401, "Missing or invalid X-API-Key header.")
    limit = int(os.getenv("RATE_LIMIT_PER_MIN", "20"))
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


class Copy(BaseModel):
    content: str
    backend: str


def _run(fn, **kwargs) -> Copy:
    llm = get_llm()
    try:
        return Copy(content=fn(llm, **kwargs), backend=llm.name)
    except ValueError as e:  # invalid campaign/platform combination
        raise HTTPException(422, str(e)) from e
    except Exception as e:  # upstream/model failure: log it, don't leak it
        log.exception("LLM call failed")
        raise HTTPException(502, "The language model could not produce copy right now. Please retry.") from e


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
    }


@app.post("/generate", response_model=Copy, dependencies=[Depends(guard)])
def generate(req: Brief) -> Copy:
    return _run(service.generate, **req.model_dump())


@app.post("/refine", response_model=Copy, dependencies=[Depends(guard)])
def refine(req: RefineRequest) -> Copy:
    return _run(service.refine, **req.model_dump())


@app.post("/translate", response_model=Copy, dependencies=[Depends(guard)])
def translate(req: TranslateRequest) -> Copy:
    return _run(service.translate, **req.model_dump())
