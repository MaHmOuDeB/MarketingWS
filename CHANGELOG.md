# Changelog

## 2.4.0 — 2026-09-28 · Fact check and clean formatting

Live tests showed the prompt alone doesn't stop invented facts: at any reasoning level the model wrote
"ready in 30 minutes", "100% recyclable" and "no credit card required" for briefs that said none of it.

- **Fact check in code** (`backend/app/guard.py`): before copy is returned, every figure and risky promise
  ("no credit card", "guarantee", "money-back", "free shipping", "#1" …) is compared with the brief, the
  user's instructions and, when refining, their feedback and draft. Anything unsupported goes back to the
  model once with the list, to become a `[placeholder]`; figures that survive are replaced in code.
  Clean copy costs no extra call; a figure the marketer typed into the feedback is theirs to keep.
- **Clean formatting for social platforms:** `**bold**` and `#` headings are removed from LinkedIn, X,
  Facebook and Instagram copy (hashtags stay); emails and blog intros keep their formatting.
- The evaluation suite uses the same check, so a failure there means something slipped through.
- 29 offline tests.

## 2.3.0 — 2026-09-28 · Free providers (Gemini, Groq, OpenRouter)

- **Chat Completions mode** for OpenAI-compatible providers: any `OPENAI_BASE_URL` other than
  api.openai.com now uses Chat Completions (what Gemini, Groq and OpenRouter implement); OpenAI itself
  keeps the Responses API. `OPENAI_API_STYLE=responses|chat` overrides the choice.
- `/health` reports such a backend as `compat:<model>`.
- "Thinking" models that return nothing within a short output limit get one retry with room to think.
- README: a no-card setup with a free Google Gemini key (`gemini-flash-latest`, an alias that follows
  Google's current Flash model, since dated model names are retired).
- A 502 now names the provider's status and a plain reason (rejected key, unknown model, quota used up,
  provider overloaded) without echoing the provider's message.
- Answers cut off by the output limit (finish reason `length`) are retried once with more room.
- `OPENAI_REASONING_EFFORT` (e.g. `low` for Groq's `openai/gpt-oss-120b`); README: Groq setup.
- **No invented facts:** the live test on Groq produced made-up statistics ("70% of students…",
  "$1,200 a semester") and offers ("no credit card required"). The system prompt now forbids invented
  figures, features and offers and asks for `[X%]`-style placeholders instead; the evaluation suite fails
  any copy containing a number the brief didn't give.

## 2.2.0 — 2026-09-28 · Claude support

- **Claude backend** (`ClaudeLLM`, Anthropic Messages API): set `ANTHROPIC_API_KEY` and the service
  generates, refines, translates and writes A/B variants with Claude. Default model `claude-haiku-4-5`
  (fast and inexpensive); any Claude model via `ANTHROPIC_MODEL`, e.g. `claude-sonnet-5`.
  If a model rejects the temperature setting, the backend retries once without it and remembers.
- **Provider choice:** `LLM_PROVIDER=openai|anthropic|demo`; by default whichever key is set (OpenAI
  first when both are). A misconfiguration (unknown provider, provider without its key) fails loudly.
- The evaluation suite runs against either provider, reads keys from `.env`, and writes one report per
  provider (`evals/report-openai.md`, `evals/report-anthropic.md`) so the two can be compared.
- The web app and Streamlit UI name the active model for either provider; demo-mode notices mention both keys.
- Tests: Claude request shape, the temperature fallback and provider selection (16 tests, offline).
- **Fix:** empty environment variables now fall back to their defaults. Vercel imports `.env.example`
  and creates the variables with empty values; an empty `RATE_LIMIT_PER_MIN` made every generate,
  refine, translate and variants request fail with a 500 on the live site, and an empty model name
  would have been sent to the provider.

## 2.1.0 — 2026-09-28 · Web app, A/B variants, evaluations, Vercel

**New features**
- **Web interface** (`public/index.html`): a responsive single-page app served together with the API, so the
  whole product runs as one deployment (Vercel, or `uvicorn server:app` locally). Light/dark theme that
  follows the system with a manual toggle, loading skeletons, toasts, a live character meter against the
  platform's limit, copy and download, keyboard shortcuts (⌘/Ctrl + Enter to generate or refine), and it
  remembers your last brief in the browser.
- **A/B variants** (`POST /variants`, "A/B variants" button): three versions of the same brief from
  deliberately different angles (benefit-led, question-led, proof-led), so an A/B test compares approaches
  instead of near-identical rewrites. Pick one and keep refining it.
- **One-click refinements:** "Shorter", "More formal", "Warmer and more personal", "Stronger call to action",
  "No hashtags", "No emojis".
- **Behavioural evaluation suite** (`evals/run_evals.py`): runs every campaign type, six refinement requests,
  two translations and the A/B variants against the real model and checks, before vs after, that the output
  changed the way it was asked (shorter is shorter, "no hashtags" removes them, the free trial gets mentioned,
  placeholders survive translation, variants really differ). Writes `evals/report.md` with the before/after texts.
- `GET /options` now also returns each platform's character limit.

**Deployment**
- `server.py`: one entry point serving the web UI at `/` and the API under `/api` (docs at `/api/docs`).
- Vercel configuration: `[tool.vercel]` entrypoint in `pyproject.toml`, `vercel.json` (function duration,
  bundle exclusions, security headers).
- The API package moved from `api/` to `backend/` (Vercel reserves `api/` for file-based functions).

**Fixes**
- The loading skeleton no longer stays on screen when a request fails.

## 2.0.0 — 2026-09-28 · Modernisation after the thesis

**Repository**
- Removed two committed virtual environments (17,799 files) and `.DS_Store`; history rewritten so the repo
  went from 134 MB to about 40 KB. All commits kept.
- The version evaluated in the thesis is preserved as the tag `thesis-2025`.
- MIT licence, `.env.example`, stricter `.gitignore`, pinned dependencies.

**API (Flask → FastAPI)**
- FastAPI with validated request models, automatic OpenAPI docs, `/health`, `/options`, `/generate`,
  `/refine`, `/translate`.
- OpenAI **Responses API** with a configurable model (`OPENAI_MODEL`, default `gpt-4.1-mini`);
  `gpt-3.5-turbo`, used by the thesis version, shuts down on 23 Oct 2026. Any OpenAI-compatible endpoint
  via `OPENAI_BASE_URL`; sampling parameters skipped for reasoning models.
- Offline **demo mode** when no API key is set, so anyone can try it and the tests need no key.
- Protection for public deployments: optional `X-API-Key`, per-IP rate limiting, input size limits,
  errors that don't leak internals (422 for invalid input, 502 for model failures).

**Behaviour fixes**
- **Refinement now revises the current draft**: the previous draft is sent back to the model with the
  feedback. The thesis version resent only the brief plus feedback, so "Improve" regenerated from scratch.
- **Translation translates the current draft** (keeping hashtags, emojis and placeholders) instead of
  generating new copy in another language.
- Every campaign type now gets the platform it needs: four templates used a platform the UI never asked
  for, producing prompts like "for  about …".
- Output budget per campaign type (the fixed 180-token cap cut off emails and blog intros).
- Channel character limits (X 280, LinkedIn 3,000, Google Ads 90 …): the model is asked to respect them,
  asked once to shorten if needed, and only then trimmed at a word boundary (not mid-word).
- System prompt rewritten (sentences previously ran together without spaces) and typos fixed.

**Interface (Streamlit)**
- Platform choice per campaign type, readable draft view, word-level diff of each revision, version
  history, translation of the current draft, developer menu hidden.

**Engineering**
- Tests (offline, fake and demo backends), ruff lint and format, GitHub Actions CI on Python 3.12 and 3.13
  plus a Docker build-and-smoke-test job.
- Python 3.12 images running as a non-root user with health checks; fixed docker-compose port mapping
  (the old compose file mapped ports the apps didn't listen on).
- README rewritten: thesis evaluation results, architecture, quick start, API, configuration, deployment.

## 1.0 — 2025 · Thesis version

Flask API + Streamlit UI on `gpt-3.5-turbo`, deployed on Google Cloud Run, evaluated with nine professional
marketers (SUS 83/100, relevance 4.6/5, fluency 4.7/5, 7 of 9 preferred it to writing manually). Tag `thesis-2025`.
