"""Tests of the FastAPI backend (stand-in embedder, fake streaming LLM client)."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from bootup import config
from bootup.build import run_build
from bootup.embed import HashingEmbedder


class FakeStreamGroq:
    """Stands in for groq.Groq with stream=True: yields the canned text in two pieces."""
    calls = []

    def __init__(self, api_key):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        FakeStreamGroq.calls.append(kw)
        grounded = "Context passages" in kw["messages"][-1]["content"]
        text = "Grounded answer citing [1]." if grounded else "Plain answer."
        half = len(text) // 2

        def part(t):
            return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=t))])
        return iter([part(text[:half]), part(text[half:])])


@pytest.fixture
def client(corpus, tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    run_build(corpus, index_dir, HashingEmbedder())
    monkeypatch.setattr(config, "EMBED_MODEL", "standin")
    monkeypatch.setattr(config, "DATA_DIR", corpus)
    monkeypatch.setattr(config, "INDEX_DIR", index_dir)
    monkeypatch.setattr(config, "RESULTS_DIR", tmp_path / "results")
    import groq
    monkeypatch.setattr(groq, "Groq", FakeStreamGroq)
    FakeStreamGroq.calls = []
    from server import api
    monkeypatch.setattr(api, "state", api.State())
    return TestClient(api.app)


def events(resp):
    """Parse a server-sent-events body into (event, data) pairs."""
    out = []
    for block in resp.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_status_reports_real_index(client):
    s = client.get("/api/status", params={"wait": True}).json()
    assert s["loading"] is False and s["chunks"] > 0 and s["modes"] == ["hybrid", "dense", "bm25"]
    assert s["embedder_is_standin"] is True


def test_ask_streams_sources_then_tokens_then_done(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    resp = client.post("/api/ask", json={"question": "What are the conditions for deadlock?"})
    ev = events(resp)
    assert ev[0][0] == "sources" and len(ev[0][1]["hits"]) > 0
    tokens = [d["t"] for e, d in ev if e == "token"]
    assert len(tokens) == 2 and "".join(tokens) == "Grounded answer citing [1]."
    assert ev[-1] == ("done", {"cited": [1]})
    assert FakeStreamGroq.calls[0]["stream"] is True


def test_ask_without_key_reports_error_but_keeps_sources(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    ev = events(client.post("/api/ask", json={"question": "deadlock"}))
    kinds = [e for e, _ in ev]
    assert kinds[0] == "sources" and "error" in kinds and kinds[-1] == "done"
    assert "GROQ_API_KEY is not set" in dict(ev)["error"]["message"]


def test_retrieval_only_makes_no_llm_call(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    ev = events(client.post("/api/ask", json={"question": "paging", "retrieval_only": True}))
    assert [e for e, _ in ev] == ["sources", "done"] and FakeStreamGroq.calls == []


def test_compare_plain_streams_second_answer(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    ev = events(client.post("/api/ask", json={"question": "deadlock", "compare_plain": True}))
    assert "".join(d["t"] for e, d in ev if e == "plain") == "Plain answer."


def test_compare_returns_three_methods(client):
    r = client.get("/api/compare", params={"q": "mutex lock"}).json()
    assert set(r["results"]) == {"hybrid", "dense", "bm25"}


def test_eval_run_names_are_restricted(client):
    assert client.get("/api/eval").json() == {"runs": []}
    assert client.get("/api/eval/..%2Fsecrets.toml").status_code == 404


def test_out_of_tokens_is_reported_not_silent(client, monkeypatch):
    """A reasoning model can spend its whole budget thinking and return no text."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    ended = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None), finish_reason="length")])
    monkeypatch.setattr(FakeStreamGroq, "_create", lambda self, **kw: iter([ended]))
    ev = events(client.post("/api/ask", json={"question": "deadlock"}))
    assert "token budget" in dict(ev)["error"]["message"]


def test_reasoning_models_get_reasoning_effort(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "LLM_MODEL", "openai/gpt-oss-20b")
    from bootup.generate import stream_answer
    from bootup.retrieve import Hit
    hit = Hit(chunk=SimpleNamespace(source_file="f", locator="p.1", topic="t", text="x"), score=1.0)
    list(stream_answer("q", [hit], model="openai/gpt-oss-20b"))
    assert FakeStreamGroq.calls[-1]["reasoning_effort"] == config.REASONING_EFFORT
    list(stream_answer("q", [hit], model="some-other-model"))
    assert "reasoning_effort" not in FakeStreamGroq.calls[-1]


def test_access_code_gates_everything_but_status(client, monkeypatch):
    from server import api
    monkeypatch.setattr(api, "ACCESS_CODE", "s3cret-code")
    s = client.get("/api/status").json()
    assert s == {"auth_required": True, "authorized": False, "public": api.PUBLIC, "course": api.COURSE_NAME}
    assert client.get("/api/stats").status_code == 401
    assert client.post("/api/ask", json={"question": "x"}).status_code == 401
    assert client.get("/api/stats", headers={"X-Access-Code": "wrong"}).status_code == 401
    ok = {"X-Access-Code": "s3cret-code"}
    assert client.get("/api/status", headers=ok).json()["authorized"] is True
    assert client.get("/api/stats", headers=ok).status_code == 200


def test_rate_limit_per_visitor(client, monkeypatch):
    from server import api
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(api, "RATE_PER_MIN", 2)
    api._recent.clear()
    a = {"X-Forwarded-For": "10.0.0.1"}
    codes = [client.post("/api/ask", json={"question": "deadlock", "retrieval_only": True}, headers=a).status_code
             for _ in range(3)]
    assert codes == [200, 200, 429]
    other = client.post("/api/ask", json={"question": "deadlock", "retrieval_only": True},
                        headers={"X-Forwarded-For": "10.0.0.2"})
    assert other.status_code == 200


def test_public_mode_blocks_rebuild(client, monkeypatch):
    from server import api
    monkeypatch.setattr(api, "PUBLIC", True)
    assert client.post("/api/build").status_code == 403


def test_bad_mode_rejected(client):
    assert client.post("/api/ask", json={"question": "x", "mode": "magic"}).status_code == 422
