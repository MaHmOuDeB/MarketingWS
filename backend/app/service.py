"""Generation, refinement and translation — the thesis workflow, independent of the web layer."""

from __future__ import annotations

import os
import re
from typing import List, Optional

from .campaigns import CAMPAIGNS, build_brief, char_limit, trim_to_limit
from .guard import lost_facts, replace_numbers, strip_markdown, unsupported_claims
from .llm import LLM, Message

SYSTEM = (
    "You are a senior marketing copywriter. Write concise, on-topic, well-structured copy that fits "
    "the campaign type, the platform and the audience. Treat the brief's structure as guidance, not a "
    "script: use your judgement to make the copy work. Follow any additional instructions from the "
    "user exactly. Use only facts from the brief and the user's instructions: never invent "
    "statistics, percentages, prices, customer numbers, product features, guarantees or offers (such "
    "as a free plan or 'no credit card required'). Where a figure would make the copy stronger, write "
    "a placeholder in square brackets, like [X%] or [number of users], for the marketer to fill in. "
    "Return only the copy itself — no preamble, no notes, no surrounding quotes. "
    "Write in {language}."
)


def system_prompt(language: str, extra: Optional[str]) -> str:
    base = SYSTEM.format(language=language)
    return f"{base}\n\nAdditional instructions from the user: {extra.strip()}" if extra and extra.strip() else base


def _limit_note(platform: Optional[str]) -> str:
    limit = char_limit(platform)
    return f" Stay within {limit} characters in total." if limit and limit < 5000 else ""


def generate(
    llm: LLM,
    *,
    campaign_type: str,
    tone: str,
    topic: str,
    audience: Optional[str],
    platform: Optional[str],
    language: str,
    extra_instructions: Optional[str],
) -> str:
    brief = build_brief(campaign_type, tone, topic, audience, platform) + _limit_note(platform)
    text = llm.complete(
        system_prompt(language, extra_instructions),
        [{"role": "user", "content": brief}],
        CAMPAIGNS[campaign_type].max_output_tokens,
    )
    facts = f"{brief}\n{extra_instructions or ''}"
    text = _checked(llm, text, facts, language, campaign_type, _review(llm, [text], facts)[0])
    return _fit(llm, strip_markdown(text, platform), platform, language, campaign_type)


ANGLES = (
    ("Benefit-led", "Lead with the single biggest benefit for the reader."),
    ("Question-led", "Open with a question that names the reader's problem."),
    (
        "Proof-led",
        "Open with a concrete fact, number or result from the brief, or a placeholder like [X%] if none is given.",
    ),
)


def variants(
    llm: LLM,
    *,
    count: int,
    campaign_type: str,
    tone: str,
    topic: str,
    audience: Optional[str],
    platform: Optional[str],
    language: str,
    extra_instructions: Optional[str],
) -> List[dict]:
    """A/B test variants: the same brief written from clearly different angles, so a test can tell
    which approach works — not three near-identical rewrites."""
    brief = build_brief(campaign_type, tone, topic, audience, platform) + _limit_note(platform)
    angles = ANGLES[: max(1, min(count, len(ANGLES)))]
    texts = [
        llm.complete(
            system_prompt(language, extra_instructions),
            [{"role": "user", "content": f"{brief}\nAngle: {how}"}],
            CAMPAIGNS[campaign_type].max_output_tokens,
        )
        for _, how in angles
    ]
    facts = f"{brief}\n{extra_instructions or ''}"
    reviews = _review(llm, texts, facts)  # one call for all variants
    out = []
    for (name, _), text, found in zip(angles, texts, reviews):
        text = _checked(llm, text, facts, language, campaign_type, found)
        out.append(
            {"angle": name, "content": _fit(llm, strip_markdown(text, platform), platform, language, campaign_type)}
        )
    return out


def refine(
    llm: LLM,
    *,
    campaign_type: str,
    tone: str,
    topic: str,
    audience: Optional[str],
    platform: Optional[str],
    language: str,
    extra_instructions: Optional[str],
    draft: str,
    feedback: str,
) -> str:
    """Revise the CURRENT draft with the marketer's feedback instead of starting again.

    The thesis version resent only the brief plus the feedback, so each "Improve" produced a fresh
    draft. Sending the draft back as the assistant's previous turn keeps what already works.
    """
    brief = build_brief(campaign_type, tone, topic, audience, platform) + _limit_note(platform)
    messages: List[Message] = [
        {"role": "user", "content": brief},
        {"role": "assistant", "content": draft},
        {
            "role": "user",
            "content": "Revise the draft above. Keep what works and change only what the "
            f"feedback asks for.\nFeedback: {feedback.strip()}",
        },
    ]
    text = llm.complete(
        system_prompt(language, extra_instructions), messages, CAMPAIGNS[campaign_type].max_output_tokens
    )
    # the draft and the feedback count as facts: a figure the marketer typed in is theirs to keep
    facts = f"{brief}\n{extra_instructions or ''}\n{draft}\n{feedback}"
    text = _checked(llm, text, facts, language, campaign_type, _review(llm, [text], facts)[0])
    return _fit(llm, strip_markdown(text, platform), platform, language, campaign_type)


def translate(llm: LLM, *, text: str, language: str, platform: Optional[str] = None) -> str:
    """Translate the current copy (not a fresh generation), keeping format, hashtags and placeholders."""
    instructions = (
        "You are a professional marketing translator. Translate faithfully and naturally, "
        "adapting idioms for native readers. Keep line breaks, hashtags, emojis, links and "
        "placeholders such as <registration_link> unchanged. Return only the translation."
    )
    prompt = f"Translate this marketing copy into {language}.{_limit_note(platform)}\n\n{text}"
    out = llm.complete(instructions, [{"role": "user", "content": prompt}], max(200, len(text) // 2))
    return trim_to_limit(strip_markdown(out, platform), char_limit(platform))


REVIEW = (
    "You check marketing copy against its brief before it is published. For each text, list the "
    "concrete claims it makes that the brief does not state or clearly imply: product features, "
    'specific benefits, offers, numbers, awards, comparisons. Persuasive but generic wording ("take '
    'control of your finances") is fine, and so are placeholders in [brackets]. Answer with exactly '
    'one line per text, quoting the copy\'s own words: "<n>: NONE" or "<n>: claim | claim". '
    "No other text."
)


def _review(llm: LLM, texts: List[str], facts: str) -> List[List[str]]:
    """A short model review that finds invented claims the pattern check can't see (a feature named
    in plain words). One call covers every text; FACT_REVIEW=off skips it."""
    if os.getenv("FACT_REVIEW", "on").strip().lower() in ("off", "0", "false", "no"):
        return [[] for _ in texts]
    numbered = "\n\n".join(f"TEXT {i}:\n{t}" for i, t in enumerate(texts, 1))
    try:
        reply = llm.complete(
            REVIEW, [{"role": "user", "content": f"BRIEF:\n{facts}\n\n{numbered}"}], 120 + 60 * len(texts)
        )
    except Exception:  # the review is a safeguard, never a reason to fail the request
        return [[] for _ in texts]
    found: List[List[str]] = [[] for _ in texts]
    for line in reply.splitlines():
        m = re.match(r"\s*(?:TEXT\s*)?(\d+)\s*[:.)-]\s*(.+)", line, re.I)
        if m and 1 <= int(m.group(1)) <= len(texts) and m.group(2).strip().upper().rstrip(".") != "NONE":
            claims = [c.strip(" \"'“”") for c in m.group(2).split("|")]
            found[int(m.group(1)) - 1] = [c for c in claims if 2 < len(c) < 120][:6]
    return found


def _checked(
    llm: LLM, text: str, facts: str, language: str, campaign_type: str, reviewed: Optional[List[str]] = None
) -> str:
    """Keep only claims the brief supports: one revision that swaps unsupported figures, promises and
    features (from the pattern check and the review) for placeholders or removes them, then — if
    figures remain — replace them in code."""
    claims = list(dict.fromkeys(unsupported_claims(text, facts) + list(reviewed or [])))
    if not claims:
        return text
    listed = ", ".join(f'"{c}"' for c in claims)
    revised = llm.complete(
        system_prompt(language, None),
        [
            {
                "role": "user",
                "content": f"BRIEF:\n{facts}\n\nThe copy below states things the brief does not support: "
                f"{listed}. Fix only those: replace an unsupported figure with a placeholder in square "
                "brackets (such as [X%]) and remove or make generic an unsupported feature or promise. Keep "
                "everything the brief states exactly as it is, including its numbers. Change nothing else. "
                "Return only the copy.\n\nCOPY:\n" + text,
            }
        ],
        CAMPAIGNS[campaign_type].max_output_tokens,
    )
    # a revision must not lose a true fact: if a figure from the brief disappeared, keep the original
    # and only replace its unsupported figures in code
    if lost_facts(text, revised, facts):
        return replace_numbers(text, facts)
    return replace_numbers(revised, facts) if unsupported_claims(revised, facts) else revised


def _fit(llm: LLM, text: str, platform: Optional[str], language: str, campaign_type: str) -> str:
    """Enforce the channel's character limit: ask the model to shorten once, then trim at a word."""
    limit = char_limit(platform)
    if limit and len(text) > limit:
        text = llm.complete(
            system_prompt(language, None),
            [
                {
                    "role": "user",
                    "content": f"Shorten this to at most {limit} characters without losing the "
                    f"call to action. Return only the copy.\n\n{text}",
                }
            ],
            CAMPAIGNS[campaign_type].max_output_tokens,
        )
    return trim_to_limit(text, limit)
