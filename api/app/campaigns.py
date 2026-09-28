"""Campaign types: the brief template, which platforms apply, and the output budget for each.

The templates come from the thesis version and were tightened after its evaluation: every
placeholder is now filled for every campaign (no more "for  about …"), and each campaign declares
its own length so emails and blog intros are no longer cut off.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

SOCIAL = ("LinkedIn", "X (Twitter)", "Facebook", "Instagram")

# Hard character limits of the channels (2026). LinkedIn allows 3,000 characters per post.
CHAR_LIMITS: Dict[str, int] = {
    "X (Twitter)": 280,
    "LinkedIn": 3000,
    "Instagram": 2200,
    "Facebook": 63206,
    "Google Ads": 90,  # one responsive-search-ad description line
    "Meta Ads": 125,  # primary text shown before "See more"
    "LinkedIn Ads": 150,  # introductory text shown before truncation
}

LANGUAGES = ("English", "German", "French", "Spanish", "Italian", "Portuguese", "Dutch")
TONES = ("professional", "friendly", "casual", "urgent", "inspiring", "serious and bright")


@dataclass(frozen=True)
class Campaign:
    label: str
    template: str
    max_output_tokens: int
    platforms: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def needs_platform(self) -> bool:
        return bool(self.platforms)


CAMPAIGNS: Dict[str, Campaign] = {
    "social_media": Campaign(
        "Social media post",
        "Create a {tone} social media post for {platform} about {topic}, written for {audience}. "
        "Open with a thought-provoking question or statistic (one sentence), highlight the main benefit "
        "(one sentence), add a clear call to action, and finish with 2–3 relevant hashtags.",
        300,
        SOCIAL,
    ),
    "email_marketing": Campaign(
        "Email",
        "Write a {tone} marketing email promoting {topic} to {audience}. Include a subject line under "
        "60 characters, a personalised greeting, two key benefits in separate short paragraphs, a strong "
        "call to action, a professional sign-off, and a P.S. that repeats the call to action.",
        650,
    ),
    "ppc_ads": Campaign(
        "PPC ad",
        "Write a {tone} {platform} ad about {topic} for {audience}. Give a headline under 30 characters "
        "on the first line and a description under 90 characters on the second line, ending with a direct "
        "call to action. Do not wrap the copy in quotes.",
        120,
        ("Google Ads", "Meta Ads", "LinkedIn Ads"),
    ),
    "content_marketing": Campaign(
        "Blog introduction",
        "Draft a {tone} blog introduction about {topic}, aimed at {audience}. Begin with an engaging "
        "statistic or question, outline three key points as a bulleted list, and end with a transition "
        "sentence into the main article.",
        550,
    ),
    "customer_retention": Campaign(
        "Re-engagement message",
        "Create a {tone} customer re-engagement message about {topic} for {audience}. Acknowledge their "
        "past engagement, mention an exclusive incentive, and close with a friendly reminder of the next "
        "step. Use at most one emoji.",
        350,
    ),
    "seasonal_campaigns": Campaign(
        "Seasonal campaign post",
        "Write a {tone} seasonal campaign post for {platform} about {topic}, written for {audience}. Open "
        "with a festive greeting, tie the message to the season, highlight one special offer or feature, "
        "and include one season-themed hashtag.",
        300,
        SOCIAL,
    ),
    "product_launch": Campaign(
        "Product launch announcement",
        "Draft a {tone} product launch announcement for {platform} about {topic}, written for {audience}. "
        "Lead with a strong headline, describe three standout features (one sentence each), and finish "
        "with a clear invitation that uses the placeholder <registration_link>.",
        400,
        SOCIAL + ("Email", "Website"),
    ),
    "crisis_management": Campaign(
        "Crisis response",
        "Compose a {tone} crisis response for {platform} about {topic}, addressed to {audience}. "
        "Acknowledge the issue, express genuine empathy, outline the corrective steps, and reassure the "
        "audience of your commitment. Keep it to three or four sentences.",
        300,
        SOCIAL + ("Email", "Website"),
    ),
}

DEFAULT_AUDIENCE = "a general audience"


def build_brief(campaign_type: str, tone: str, topic: str, audience: Optional[str], platform: Optional[str]) -> str:
    """The user-facing brief for one piece of copy. Raises ValueError on an invalid combination."""
    campaign = CAMPAIGNS.get(campaign_type)
    if campaign is None:
        raise ValueError(f"Unknown campaign_type {campaign_type!r}. Choose one of: {', '.join(CAMPAIGNS)}")
    if campaign.needs_platform:
        if platform not in campaign.platforms:
            raise ValueError(f"{campaign.label} needs a platform: one of {', '.join(campaign.platforms)}")
    elif platform:
        platform = None  # platform-free campaigns ignore it rather than failing
    return campaign.template.format(
        tone=tone, topic=topic.strip(), platform=platform or "", audience=(audience or "").strip() or DEFAULT_AUDIENCE
    )


def char_limit(platform: Optional[str]) -> Optional[int]:
    return CHAR_LIMITS.get(platform or "")


def trim_to_limit(text: str, limit: Optional[int]) -> str:
    """Last-resort trim at a word boundary (the model is asked to respect the limit first)."""
    if not limit or len(text) <= limit:
        return text
    cut = text[: limit - 1]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit * 0.6 else cut).rstrip(" ,;:-") + "…"
