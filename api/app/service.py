"""Generation, refinement and translation — the thesis workflow, independent of the web layer."""

from __future__ import annotations

from typing import List, Optional

from .campaigns import CAMPAIGNS, build_brief, char_limit, trim_to_limit
from .llm import LLM, Message

SYSTEM = (
    "You are a senior marketing copywriter. Write concise, on-topic, well-structured copy that fits "
    "the campaign type, the platform and the audience. Treat the brief's structure as guidance, not a "
    "script: use your judgement to make the copy work. Follow any additional instructions from the "
    "user exactly. Return only the copy itself — no preamble, no notes, no surrounding quotes. "
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
