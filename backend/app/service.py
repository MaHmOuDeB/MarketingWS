"""Generation, refinement and translation — the thesis workflow, independent of the web layer."""

from __future__ import annotations

from typing import List, Optional

from .campaigns import CAMPAIGNS, build_brief, char_limit, trim_to_limit
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
    return _fit(llm, text, platform, language, campaign_type)


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
    out = []
    for name, how in ANGLES[: max(1, min(count, len(ANGLES)))]:
        text = llm.complete(
            system_prompt(language, extra_instructions),
            [{"role": "user", "content": f"{brief}\nAngle: {how}"}],
            CAMPAIGNS[campaign_type].max_output_tokens,
        )
        out.append({"angle": name, "content": _fit(llm, text, platform, language, campaign_type)})
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
    return _fit(llm, text, platform, language, campaign_type)


def translate(llm: LLM, *, text: str, language: str, platform: Optional[str] = None) -> str:
    """Translate the current copy (not a fresh generation), keeping format, hashtags and placeholders."""
    instructions = (
        "You are a professional marketing translator. Translate faithfully and naturally, "
        "adapting idioms for native readers. Keep line breaks, hashtags, emojis, links and "
        "placeholders such as <registration_link> unchanged. Return only the translation."
    )
    prompt = f"Translate this marketing copy into {language}.{_limit_note(platform)}\n\n{text}"
    out = llm.complete(instructions, [{"role": "user", "content": prompt}], max(200, len(text) // 2))
    return trim_to_limit(out, char_limit(platform))


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
