"""API tests. They run offline: the demo backend or a recording fake stands in for OpenAI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main, service
from app.campaigns import CAMPAIGNS, build_brief, trim_to_limit
from app.llm import DemoLLM, OpenAILLM


class Recorder:
    """Fake LLM that records what it was sent and returns a fixed reply."""

    name = "recorder"

    def __init__(self, reply="Fresh copy #tag"):
        self.calls, self.reply = [], reply

    def complete(self, instructions, messages, max_output_tokens):
        self.calls.append({"instructions": instructions, "messages": messages, "max": max_output_tokens})
        return self.reply


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("APP_API_KEY", raising=False)
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "1000")
    main._llm = DemoLLM()
    main._hits.clear()
    return TestClient(main.app)


BRIEF = {
    "campaign_type": "social_media",
    "tone": "friendly",
    "topic": "a budgeting app for students",
    "audience": "university students",
    "platform": "LinkedIn",
    "language": "English",
}


def test_health_and_options(client):
    assert client.get("/health").json() == {"status": "ok", "backend": "demo"}
    opts = client.get("/options").json()
    assert set(opts["campaigns"]) == set(CAMPAIGNS)
    assert opts["campaigns"]["email_marketing"]["platforms"] == []
    assert "Google Ads" in opts["campaigns"]["ppc_ads"]["platforms"]


def test_generate_refine_translate_flow(client):
    first = client.post("/generate", json=BRIEF).json()
    assert first["backend"] == "demo" and "budgeting app" in first["content"]
    refined = client.post("/refine", json={**BRIEF, "draft": first["content"], "feedback": "shorter"}).json()
    assert refined["content"].startswith(first["content"])  # the draft was revised, not replaced
    translated = client.post("/translate", json={"text": refined["content"], "language": "German"}).json()
    assert "German" in translated["content"]


def test_refine_sends_the_previous_draft_to_the_model():
    fake = Recorder("Revised copy")
    service.refine(fake, **BRIEF, extra_instructions=None, draft="OLD DRAFT", feedback="add a CTA")
    msgs = fake.calls[0]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[1]["content"] == "OLD DRAFT" and "add a CTA" in msgs[2]["content"]


def test_every_campaign_fills_every_placeholder():
    for key, c in CAMPAIGNS.items():
        brief = build_brief(key, "casual", "summer sale", None, c.platforms[0] if c.platforms else None)
        assert "{" not in brief and "  " not in brief and "for  " not in brief, key
        assert "a general audience" in brief or "audience" not in c.template, key


def test_validation_errors_are_clear(client):
    bad_platform = client.post("/generate", json={**BRIEF, "platform": "MySpace"})
    assert bad_platform.status_code == 422 and "needs a platform" in bad_platform.json()["detail"]
    assert client.post("/generate", json={**BRIEF, "campaign_type": "fax"}).status_code == 422
    assert client.post("/generate", json={**BRIEF, "topic": "x" * 5000}).status_code == 422
    # platform-free campaigns ignore a platform instead of failing
    ok = client.post("/generate", json={**BRIEF, "campaign_type": "email_marketing"})
    assert ok.status_code == 200


def test_channel_limit_is_enforced_at_a_word_boundary():
    fake = Recorder("word " * 200)
    out = service.generate(fake, **{**BRIEF, "platform": "X (Twitter)"}, extra_instructions=None)
    assert len(out) <= 280 and out.endswith("…") and not out.endswith(" …")
    assert len(fake.calls) == 2  # it first asked the model to shorten
    assert trim_to_limit("short", 280) == "short"


def test_model_failure_is_a_502_without_leaking_details(client):
    class Broken:
        name = "broken"

        def complete(self, *a, **k):
            raise RuntimeError("secret upstream detail")

    main._llm = Broken()
    r = client.post("/generate", json=BRIEF)
    assert r.status_code == 502 and "secret" not in r.text


def test_api_key_and_rate_limit(client, monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "s3cret")
    assert client.post("/generate", json=BRIEF).status_code == 401
    assert client.post("/generate", json=BRIEF, headers={"X-API-Key": "s3cret"}).status_code == 200
    monkeypatch.delenv("APP_API_KEY")
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "2")
    main._hits.clear()
    codes = [client.post("/generate", json=BRIEF).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_openai_backend_uses_responses_api_and_skips_temperature_for_reasoning_models(monkeypatch):
    sent = {}

    class FakeResponses:
        def create(self, **kwargs):
            sent.update(kwargs)
            return type("R", (), {"output_text": '"Hello"'})()

    llm = OpenAILLM.__new__(OpenAILLM)
    llm.client = type("C", (), {"responses": FakeResponses()})()
    llm.model, llm.temperature, llm.name = "gpt-4.1-mini", 0.7, "openai:gpt-4.1-mini"
    assert llm.complete("sys", [{"role": "user", "content": "hi"}], 100) == "Hello"
    assert sent["instructions"] == "sys" and sent["max_output_tokens"] == 100 and sent["temperature"] == 0.7
    llm.model = "gpt-5.6-terra"
    sent.clear()
    llm.complete("sys", [{"role": "user", "content": "hi"}], 100)
    assert "temperature" not in sent
