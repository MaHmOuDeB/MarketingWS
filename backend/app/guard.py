"""Checks on generated copy that the prompt alone does not guarantee.

Models asked not to invent facts still do: live tests produced "70% of students…", "ready in 30
minutes" and "no credit card required" for briefs that said none of it. In marketing copy an
invented statistic or offer is a legal and trust problem, so every draft is checked in code:

unsupported_claims  numbers and risky promises in the copy that the brief never gave
strip_markdown      **bold** / # headings, which social platforms show as literal characters
"""

from __future__ import annotations

import re
from typing import List

# placeholders the model is told to use, e.g. [X%], [number of users], <registration_link>
PLACEHOLDER = re.compile(r"\[[^\]\n]{0,60}\]|<[^>\n]{0,60}>")
NUMBER = re.compile(r"(?<![\w#])\d+(?:[.,]\d+)*")
# promises that create obligations; flagged only when the brief doesn't state them
RISKY = (
    "no credit card",
    "money-back",
    "money back",
    "guarantee",
    "risk-free",
    "free shipping",
    "cancel anytime",
    "lifetime",
    "award-winning",
    "clinically",
    "certified",
    "#1",
    "number one",
    "best-selling",
)
SOCIAL = {"LinkedIn", "X (Twitter)", "Facebook", "Instagram"}


def _digits(n: str) -> str:
    return re.sub(r"[.,]", "", n)


def unsupported_claims(text: str, facts: str) -> List[str]:
    """Figures and risky promises in `text` that do not appear in `facts` (the brief, the user's
    instructions and feedback). Placeholders are ignored; 1,200 and 1200 count as the same number."""
    given = {_digits(n) for n in NUMBER.findall(facts)}
    body = PLACEHOLDER.sub(" ", text)
    found = []
    for n in NUMBER.findall(body):
        if _digits(n) not in given and n not in found:
            found.append(n)
    low_text, low_facts = body.lower(), facts.lower()
    found += [p for p in RISKY if p in low_text and p not in low_facts]
    return found


def lost_facts(before: str, after: str, facts: str) -> List[str]:
    """Figures from the brief that were in `before` but are missing from `after` (a revision that
    swapped a true fact for a placeholder)."""
    given = {_digits(n) for n in NUMBER.findall(facts)}
    kept = {_digits(n) for n in NUMBER.findall(PLACEHOLDER.sub(" ", after))}
    had = [n for n in NUMBER.findall(PLACEHOLDER.sub(" ", before)) if _digits(n) in given]
    return [n for n in dict.fromkeys(had) if _digits(n) not in kept]


def replace_numbers(text: str, facts: str) -> str:
    """Last resort: turn each unsupported figure into a placeholder the marketer fills in."""
    given = {_digits(n) for n in NUMBER.findall(facts)}
    parts = PLACEHOLDER.split(text)
    holders = PLACEHOLDER.findall(text)

    def fix(chunk: str) -> str:
        return NUMBER.sub(lambda m: m.group(0) if _digits(m.group(0)) in given else "[X]", chunk)

    out = fix(parts[0])
    for holder, part in zip(holders, parts[1:]):
        out += holder + fix(part)
    return out


def strip_markdown(text: str, platform: str | None) -> str:
    """Social platforms don't render Markdown: remove bold/italic markers and heading hashes
    (hashtags like #StudentFinance stay)."""
    if platform not in SOCIAL:
        return text
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text)
    return re.sub(r"(?m)^#{1,6}\s+", "", text)
