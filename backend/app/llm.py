"""Language-model backends.

OpenAILLM   uses the OpenAI Responses API (the current API; Chat Completions is legacy).
            Model, base URL and temperature come from the environment, so the service keeps
            working when OpenAI retires a model: gpt-3.5-turbo, used in the thesis version, shuts
            down on 23 Oct 2026. Any OpenAI-compatible endpoint works via OPENAI_BASE_URL.
ClaudeLLM   uses Anthropic's Messages API (Claude). Model and temperature from the environment.
DemoLLM     deterministic, offline copy for trying the app and for tests — no key, no cost.

Which backend runs (from_env): LLM_PROVIDER=openai|anthropic|demo if set; otherwise the provider
whose API key is set (OpenAI first when both are); otherwise demo mode.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Protocol

Message = dict  # {"role": "user" | "assistant", "content": str}

DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5"  # fast and inexpensive; claude-sonnet-5 for higher quality


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


class ClaudeLLM:
    def __init__(self, api_key: str, model: Optional[str] = None, temperature: Optional[float] = None):
        from anthropic import Anthropic  # imported lazily so the other backends don't need the SDK

        self.client = Anthropic(api_key=api_key, timeout=45.0, max_retries=2)
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_CLAUDE_MODEL)
        t = os.getenv("ANTHROPIC_TEMPERATURE")
        self.temperature: Optional[float] = temperature if temperature is not None else (float(t) if t else 0.7)
        self.name = f"anthropic:{self.model}"

    def complete(self, instructions: str, messages: List[Message], max_output_tokens: int) -> str:
        kwargs = {
            "model": self.model,
            "system": instructions,
            "messages": messages,
            "max_tokens": max_output_tokens,
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        try:
            response = self.client.messages.create(**kwargs)
        except Exception as e:
            # some models fix their sampling parameters: retry once without temperature, then remember
            if "temperature" not in kwargs or "temperature" not in str(e).lower():
                raise
            self.temperature = None
            kwargs.pop("temperature")
            response = self.client.messages.create(**kwargs)
        return clean("".join(b.text for b in response.content if getattr(b, "type", "") == "text"))


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
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes") or provider == "demo":
        return DemoLLM()
    if provider in ("anthropic", "claude"):
        if not anthropic_key:
            raise RuntimeError("LLM_PROVIDER=anthropic needs ANTHROPIC_API_KEY")
        return ClaudeLLM(anthropic_key)
    if provider == "openai":
        if not openai_key:
            raise RuntimeError("LLM_PROVIDER=openai needs OPENAI_API_KEY")
        return OpenAILLM(openai_key)
    if provider:
        raise RuntimeError(f"unknown LLM_PROVIDER {provider!r}: use openai, anthropic or demo")
    if openai_key:
        return OpenAILLM(openai_key)
    if anthropic_key:
        return ClaudeLLM(anthropic_key)
    return DemoLLM()
