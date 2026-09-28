"""Behavioural evaluation against the real model: does the output change the way the brief or the
feedback asks?

    OPENAI_API_KEY=... python evals/run_evals.py            # prints a table, writes evals/report-openai.md
    ANTHROPIC_API_KEY=... python evals/run_evals.py         # the same checks against Claude
    python evals/run_evals.py                               # uses the keys in .env (LLM_PROVIDER picks one)

Unit tests (tests/) prove the plumbing with a fake model. This suite checks the *model's behaviour*:
every campaign type fills its structure and channel limit, each refinement changes the draft in the
requested direction while keeping the rest, translation keeps placeholders and hashtags, and A/B
variants really differ. It costs a few cents per run, so it is not part of CI.
"""

from __future__ import annotations

import difflib
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import service  # noqa: E402
from app.campaigns import CAMPAIGNS, CHAR_LIMITS  # noqa: E402
from app.guard import unsupported_claims  # noqa: E402
from app.llm import from_env  # noqa: E402

EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿]")
BASE = dict(
    tone="friendly",
    topic="Budgetly, a budgeting app that helps students track spending; 14-day free trial",
    audience="university students",
    language="English",
    extra_instructions=None,
)


def invented_figures(text: str, brief: str) -> list:
    """Figures and risky promises the brief never gave (placeholders like [X%] are fine) — the same
    check the service applies before returning copy, so a failure here means it slipped through."""
    return sorted(unsupported_claims(text, brief))


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(a=a.split(), b=b.split()).ratio()


def words(t: str) -> int:
    return len(t.split())


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """KEY=value lines from .env, without overriding the real environment (no extra dependency)."""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            key, value = key.strip(), value.split(" #", 1)[0].strip().strip("'\"")
            if sep and key and not key.startswith("#") and value:
                os.environ.setdefault(key, value)


def run(llm) -> list:
    results = []

    def check(area, case, ok, detail, before="", after=""):
        results.append({"area": area, "case": case, "ok": bool(ok), "detail": detail, "before": before, "after": after})
        print(f"{'PASS' if ok else 'FAIL'}  {area:<10} {case:<38} {detail}")

    # 1. every campaign type: structure + channel limit
    for key, c in CAMPAIGNS.items():
        platform = c.platforms[0] if c.platforms else None
        if key == "social_media":
            platform = "X (Twitter)"
        text = service.generate(llm, campaign_type=key, platform=platform, **BASE)
        limit = CHAR_LIMITS.get(platform or "")
        ok = bool(text.strip()) and "{" not in text and (not limit or len(text) <= limit)
        extra = ""
        if key == "email_marketing":
            ok &= bool(re.search(r"subject", text, re.I)) and "P.S" in text
            extra = "subject + P.S."
        if key == "ppc_ads":
            lines = [ln for ln in text.splitlines() if ln.strip()]
            ok &= len(lines) >= 2 and len(lines[0]) <= 30
            extra = f"headline {len(lines[0]) if lines else 0} chars"
        if key == "product_launch":
            ok &= "<registration_link>" in text
            extra = "placeholder kept"
        made_up = invented_figures(text, BASE["topic"] + " " + (platform or ""))
        ok &= not made_up
        if made_up:
            extra += f"{'; ' if extra else ''}invented figures: {', '.join(made_up)}"
        check(
            "generate",
            c.label,
            ok,
            f"{len(text)} chars" + (f" / limit {limit}" if limit else "") + (f"; {extra}" if extra else ""),
            after=text,
        )

    # 2. refinement: before vs after, per feedback
    brief = dict(campaign_type="social_media", platform="LinkedIn", **BASE)
    draft = service.generate(llm, **brief)
    cases = [
        ("Make it much shorter", lambda b, a: words(a) < 0.75 * words(b), "words {wb} → {wa}"),
        ("Remove all hashtags", lambda b, a: "#" not in a and "#" in b, "hashtags {hb} → {ha}"),
        ("No emojis at all", lambda b, a: not EMOJI.search(a), "emojis {eb} → {ea}"),
        (
            "Mention the 14-day free trial explicitly",
            lambda b, a: "14" in a and "trial" in a.lower(),
            "mentions trial: {tb} → {ta}",
        ),
        ("Add a question as the first sentence", lambda b, a: "?" in a.split(".")[0][:200], "opens with a question"),
        ("Use a more formal tone", lambda b, a: similarity(b, a) < 0.95, "similarity {sim:.2f} (<0.95 = changed)"),
    ]
    for fb, test, fmt in cases:
        after = service.refine(llm, draft=draft, feedback=fb, **brief)
        sim = similarity(draft, after)
        detail = fmt.format(
            wb=words(draft),
            wa=words(after),
            hb=draft.count("#"),
            ha=after.count("#"),
            eb=len(EMOJI.findall(draft)),
            ea=len(EMOJI.findall(after)),
            tb="trial" in draft.lower(),
            ta="trial" in after.lower(),
            sim=sim,
        )
        # a refinement should change what was asked and keep the rest: not a brand-new text
        kept = sim > 0.2 or fb.startswith(("Make it much shorter", "Use a more formal"))
        check("refine", fb, test(draft, after) and kept, f"{detail}; kept {sim:.0%} of wording", draft, after)

    # 3. translation keeps what must not change
    launch = service.generate(llm, campaign_type="product_launch", platform="LinkedIn", **BASE)
    for lang, marker in (("German", r"\b(und|der|die|das|mit|für)\b"), ("French", r"\b(et|le|la|les|pour|avec)\b")):
        tr = service.translate(llm, text=launch, language=lang, platform="LinkedIn")
        ok = bool(re.search(marker, tr, re.I)) and "<registration_link>" in tr and tr.count("#") == launch.count("#")
        check(
            "translate",
            f"→ {lang}",
            ok,
            f"placeholder kept: {'<registration_link>' in tr}; hashtags {launch.count('#')} → {tr.count('#')}",
            launch,
            tr,
        )

    # 4. A/B variants are genuinely different
    vs = service.variants(llm, count=3, campaign_type="social_media", platform="LinkedIn", **BASE)
    made_up = sorted({n for v in vs for n in invented_figures(v["content"], BASE["topic"])})
    check("variants", "no invented figures", not made_up, ", ".join(made_up) or "only brief facts and [placeholders]")
    sims = [similarity(vs[i]["content"], vs[j]["content"]) for i in range(3) for j in range(i + 1, 3)]
    check(
        "variants",
        "3 angles differ",
        len(vs) == 3 and max(sims) < 0.6,
        f"max pairwise similarity {max(sims):.2f}",
        after="\n\n---\n\n".join(f"{v['angle']}: {v['content']}" for v in vs),
    )
    return results


def report(results: list, model: str) -> str:
    passed = sum(r["ok"] for r in results)
    lines = [
        f"# Evaluation report\n\nModel: `{model}` · "
        f"{time.strftime('%Y-%m-%d %H:%M')} · **{passed}/{len(results)} checks passed**\n",
        "| Area | Case | Result | Detail |",
        "|---|---|---|---|",
    ]
    lines += [f"| {r['area']} | {r['case']} | {'✅' if r['ok'] else '❌'} | {r['detail']} |" for r in results]
    lines.append("\n## Before → after (refinement)\n")
    for r in results:
        if r["area"] == "refine":
            lines += [
                f"### {r['case']}\n",
                "**Before**\n",
                f"> {r['before']}\n".replace("\n", "\n> ").rstrip("> "),
                "**After**\n",
                f"> {r['after']}\n".replace("\n", "\n> ").rstrip("> "),
            ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    load_dotenv()
    llm = from_env()
    if llm.name == "demo":
        sys.exit(
            "Set OPENAI_API_KEY or ANTHROPIC_API_KEY (in the environment or .env) to run the behavioural "
            "evaluation; the unit tests run without a key."
        )
    print(f"Evaluating {llm.name}\n")
    res = run(llm)
    out = ROOT / "evals" / f"report-{llm.name.split(':')[0]}.md"
    out.write_text(report(res, llm.name), encoding="utf-8")
    print(f"\n{sum(r['ok'] for r in res)}/{len(res)} passed · report: {out.relative_to(ROOT)}")
    sys.exit(0 if all(r["ok"] for r in res) else 1)
