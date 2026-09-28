"""Single-process entry point: the web UI at "/" and the API under "/api".

Used by Vercel (see [tool.vercel] in pyproject.toml) and for running everything locally with one command:

    uvicorn server:app --reload

On Vercel the files in public/ are served by the CDN; locally they are served by FastAPI.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app as api  # noqa: E402

app = FastAPI(title="Marketing Content Generator", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", api)
if (ROOT / "public").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "public", html=True), name="web")
