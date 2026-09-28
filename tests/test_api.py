"""API tests. They run offline: the demo backend or a recording fake stands in for OpenAI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main, service
from app.campaigns import CAMPAIGNS, build_brief, trim_to_limit
from app.llm import ClaudeLLM, DemoLLM, OpenAILLM, from_env


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
    llm.style = "responses"
    assert llm.complete("sys", [{"role": "user", "content": "hi"}], 100) == "Hello"
    assert sent["instructions"] == "sys" and sent["max_output_tokens"] == 100 and sent["temperature"] == 0.7
    llm.model = "gpt-5.6-terra"
    sent.clear()
    llm.complete("sys", [{"role": "user", "content": "hi"}], 100)
    assert "temperature" not in sent


def _fake_claude(model="claude-haiku-4-5", reject_temperature=False):
    sent = []

    class FakeMessages:
        def create(self, **kwargs):
            sent.append(kwargs)
            if reject_temperature and "temperature" in kwargs:
                raise RuntimeError("temperature is not supported for this model")
            blocks = [type("B", (), {"type": "text", "text": '"Hello from Claude"'})()]
            return type("R", (), {"content": blocks})()

    llm = ClaudeLLM.__new__(ClaudeLLM)
    llm.client = type("C", (), {"messages": FakeMessages()})()
    llm.model, llm.temperature, llm.name = model, 0.7, f"anthropic:{model}"
    return llm, sent


def test_claude_backend_uses_messages_api():
    llm, sent = _fake_claude()
    history = [
        {"role": "user", "content": "brief"},
        {"role": "assistant", "content": "draft"},
        {"role": "user", "content": "Feedback: shorter"},
    ]
    assert llm.complete("sys", history, 300) == "Hello from Claude"
    assert sent[0]["system"] == "sys" and sent[0]["messages"] == history
    assert sent[0]["max_tokens"] == 300 and sent[0]["temperature"] == 0.7


def test_claude_backend_drops_temperature_when_the_model_rejects_it():
    llm, sent = _fake_claude(reject_temperature=True)
    assert llm.complete("sys", [{"role": "user", "content": "hi"}], 100) == "Hello from Claude"
    assert "temperature" in sent[0] and "temperature" not in sent[1]
    llm.complete("sys", [{"role": "user", "content": "hi"}], 100)  # remembered: one call, no retry
    assert len(sent) == 3 and "temperature" not in sent[2]


def test_provider_selection(monkeypatch):
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_PROVIDER", "DEMO_MODE"):
        monkeypatch.delenv(k, raising=False)
    assert from_env().name == "demo"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert from_env().name == "anthropic:claude-haiku-4-5"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert from_env().name.startswith("openai:")  # both keys: OpenAI unless LLM_PROVIDER says otherwise
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5")
    assert from_env().name == "anthropic:claude-sonnet-5"
    monkeypatch.setenv("LLM_PROVIDER", "demo")
    assert from_env().name == "demo"
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(RuntimeError):
        from_env()


def test_variants_are_distinct_angles(client):
    r = client.post("/variants", json={**BRIEF, "count": 3}).json()
    assert [v["angle"] for v in r["variants"]] == ["Benefit-led", "Question-led", "Proof-led"]
    assert len({v["content"] for v in r["variants"]}) == 3
    assert client.post("/variants", json={**BRIEF, "count": 7}).status_code == 422


def test_options_expose_channel_limits(client):
    assert client.get("/options").json()["char_limits"]["X (Twitter)"] == 280


def test_single_entrypoint_serves_web_ui_and_api(monkeypatch):
    import server

    main._llm = DemoLLM()
    main._hits.clear()
    web = TestClient(server.app)
    page = web.get("/")
    assert page.status_code == 200 and "Marketing Content Generator" in page.text
    assert web.get("/api/health").json()["status"] == "ok"
    assert web.post("/api/generate", json=BRIEF).status_code == 200
    assert web.get("/api/docs").status_code == 200


def test_empty_environment_variables_fall_back_to_defaults(monkeypatch, client):
    # Vercel imports .env.example, creating these variables with empty values
    for k in (
        "RATE_LIMIT_PER_MIN",
        "APP_API_KEY",
        "OPENAI_MODEL",
        "ANTHROPIC_MODEL",
        "LLM_PROVIDER",
        "OPENAI_TEMPERATURE",
        "ANTHROPIC_TEMPERATURE",
        "CORS_ORIGINS",
    ):
        monkeypatch.setenv(k, "")
    main._hits.clear()
    assert client.post("/generate", json=BRIEF).status_code == 200
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    llm = from_env()
    assert llm.name == "anthropic:claude-haiku-4-5" and llm.temperature == 0.7


def _fake_chat(outputs):
    sent = []

    class FakeCompletions:
        def create(self, **kwargs):
            sent.append(kwargs)
            out = outputs[len(sent) - 1]
            text, finish = out if isinstance(out, tuple) else (out, "stop")
            msg = type("M", (), {"content": text})()
            return type("R", (), {"choices": [type("Ch", (), {"message": msg, "finish_reason": finish})()]})()

    chat = type("Chat", (), {"completions": FakeCompletions()})()
    return type("C", (), {"chat": chat})(), sent


def test_compatible_providers_use_chat_completions(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "LLM_PROVIDER", "DEMO_MODE", "OPENAI_API_STYLE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "free-tier-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    monkeypatch.setenv("OPENAI_MODEL", "gemini-2.5-flash")
    llm = from_env()
    assert llm.name == "compat:gemini-2.5-flash" and llm.style == "chat"
    llm.client, sent = _fake_chat(['"Budget smarter."'])
    assert llm.complete("sys", [{"role": "user", "content": "brief"}], 180) == "Budget smarter."
    assert sent[0]["messages"][0] == {"role": "system", "content": "sys"}
    assert sent[0]["max_tokens"] == 180 and sent[0]["temperature"] == 0.7
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    assert from_env().style == "responses"  # OpenAI itself keeps the Responses API


def test_chat_retries_with_room_to_think_when_output_is_empty(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    llm = OpenAILLM("k", model="some-thinking-model")
    llm.client, sent = _fake_chat(["", "Copy after thinking."])
    assert llm.complete("sys", [{"role": "user", "content": "brief"}], 180) == "Copy after thinking."
    assert [s["max_tokens"] for s in sent] == [180, 2048]


def test_model_failure_says_why_without_leaking_the_provider_message(client):
    class QuotaError(Exception):
        status_code = 429

    class Failing:
        name = "compat:gemini-2.5-flash"

        def complete(self, *a, **k):
            raise QuotaError("quota exceeded for key sk-secret-123")

    main._llm = Failing()
    main._hits.clear()
    r = client.post("/generate", json=BRIEF)
    assert r.status_code == 502 and "429" in r.json()["detail"] and "quota" in r.json()["detail"]
    assert "sk-secret" not in r.text
    main._llm = DemoLLM()


def test_chat_retries_when_the_answer_is_cut_off(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    llm = OpenAILLM("k", model="gemini-flash-latest")
    llm.client, sent = _fake_chat([("Ever wonder where your student loan", "length"), "The whole post."])
    assert llm.complete("sys", [{"role": "user", "content": "brief"}], 180) == "The whole post."
    assert [s["max_tokens"] for s in sent] == [180, 2048]


def test_reasoning_effort_is_passed_only_when_set(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    llm = OpenAILLM("k", model="openai/gpt-oss-120b")
    llm.client, sent = _fake_chat(["One.", "Two."])
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)
    llm.complete("sys", [{"role": "user", "content": "brief"}], 180)
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "low")
    llm.complete("sys", [{"role": "user", "content": "brief"}], 180)
    assert "reasoning_effort" not in sent[0] and sent[1]["reasoning_effort"] == "low"
