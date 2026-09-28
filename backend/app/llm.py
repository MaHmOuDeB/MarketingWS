"""Language-model backends.

OpenAILLM   uses the OpenAI Responses API (the current API; Chat Completions is legacy).
            Model, base URL and temperature come from the environment, so the service keeps
            working when OpenAI retires a model: gpt-3.5-turbo, used in the thesis version, shuts
            down on 23 Oct 2026. Any OpenAI-compatible endpoint works via OPENAI_BASE_URL.
DemoLLM     deterministic, offline copy for trying the app and for tests — no key, no cost.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Protocol

Message = dict  # {"role": "user" | "assistant", "content": str}

DEFAULT_MODEL = "gpt-4.1-mini"


class LLM(Protocol):
    name: str

    def complete(self, instructions: str, messages: List[Message], max_output_tokens: int) -> str: ...


class OpenAILLM:
    def __init__(self, api_key: str, model: Optional[str] = None, temperature: Optional[float] = None):
        from openai import OpenAI  # imported lazily so demo mode needs no SDK configuration

        self.client = OpenAI(api_key=api_key, timeout=45.0, max_retries=2)
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        t = os.getenv("OPENAI_TEMPERATURE")
        self.temperature = temperature if temperature is not None else (float(t) if t else 0.7)
        self.name = f"openai:{self.model}"

    def _supports_temperature(self) -> bool:
        # reasoning models (o-series, gpt-5.x) reject sampling parameters
        return not re.match(r"^(o\d|gpt-5)", self.model)

    def complete(self, instructions: str, messages: List[Message], max_output_tokens: int) -> str:
        kwargs = {
            "model": self.model,
            "instructions": instructions,
            "input": messages,
            "max_output_tokens": max_output_tokens,
        }
        if self._supports_temperature():
            kwargs["temperature"] = self.temperature
        response = self.client.responses.create(**kwargs)
        return clean(response.output_text)


class DemoLLM:
    """Offline stand-in: builds plausible copy from the brief so every screen can be tried."""

    name = "demo"

    def complete(self, instructions: str, messages: List[Message], max_output_tokens: int) -> str:
        last = messages[-1]["content"]
        if last.startswith("Translate"):
            lang = re.search(r"into (\w+)", last)
            draft = last.split("\n\n", 1)[-1]
            return f"[{lang.group(1) if lang else 'Translated'} · demo] {draft}"
        if len(messages) > 1:  # refine: draft + feedback
            draft = messages[-2]["content"]
            feedback = last.split("Feedback:", 1)[-1].strip().splitlines()[0]
            return f"{draft}\n\n(Revised for: {feedback}) [demo]"
        topic = re.search(r"about (.+?)(?:,| for | to |\.)", last)
        subject = topic.group(1) if topic else "your offer"
        if "Angle: Open with a question" in last:
            return f"Still guessing where it all goes? {subject.capitalize()} shows you in seconds. Try it free. [demo]"
        if "Angle: Open with a concrete fact" in last:
            return f"[X%] of users say {subject} changed how they plan. See why — start today. [demo]"
        return (
            f"Ready to rethink {subject}? Here's the one change that makes it easier. "
            f"Discover how {subject} saves you time from day one — try it today. "
            f"#Marketing #Growth [demo]"
        )


def clean(text: str) -> str:
    return text.strip().strip('"').strip("'").strip()


def from_env() -> LLM:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key and os.getenv("DEMO_MODE", "").lower() not in ("1", "true", "yes"):
        return OpenAILLM(key)
    return DemoLLM()
