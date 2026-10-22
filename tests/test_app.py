"""Headless tests of the Streamlit demo app (stand-in embedder, fake LLM client)."""
import json
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from bootup import config
from bootup.build import run_build
from bootup.embed import HashingEmbedder


class FakeGroq:
    """Stands in for groq.Groq: records calls, returns canned text."""
    calls = []

    def __init__(self, api_key):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        FakeGroq.calls.append(kw)
        grounded = "Context passages" in kw["messages"][-1]["content"]
        text = "Grounded answer citing [1]." if grounded else "Plain answer without sources."
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


@pytest.fixture
def app_env(corpus, tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    run_build(corpus, index_dir, HashingEmbedder())
    monkeypatch.setattr(config, "EMBED_MODEL", "standin")
    monkeypatch.setattr(config, "DATA_DIR", corpus)
    monkeypatch.setattr(config, "INDEX_DIR", index_dir)
    monkeypatch.setattr(config, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(config, "DEMO_QUESTIONS", ["How does the banker's algorithm check safety?"])
    import groq
    monkeypatch.setattr(groq, "Groq", FakeGroq)
    FakeGroq.calls = []
    return tmp_path


def without_key(monkeypatch, folder):
    """No GROQ_API_KEY: unset it and run from a folder without .streamlit/secrets.toml,
    so a developer's real key in the project folder does not leak into the test."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.chdir(folder)


def run_app():
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    assert not at.exception, at.exception
    return at


def test_app_loads_with_all_tabs(app_env, monkeypatch):
    without_key(monkeypatch, app_env)
    at = run_app()
    assert [t.label for t in at.tabs] == ["Ask", "History", "Compare retrieval", "Dataset",
                                          "Evaluation", "How it works"]
    assert any("not set" in c.value for c in at.sidebar.caption)


def test_example_button_without_key_shows_sources(app_env, monkeypatch):
    without_key(monkeypatch, app_env)
    at = run_app()
    at.button(key="example_0").click().run()
    assert not at.exception
    assert any("GROQ_API_KEY is not set" in w.value for w in at.warning)
    assert any(e.label.startswith("Sources: 4 passages") for e in at.expander)


def test_grounded_and_plain_answers_side_by_side(app_env, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    at = run_app()
    at.sidebar.toggle[0].set_value(True).run()     # also show plain LLM answer
    at.chat_input[0].set_value("What are the conditions for deadlock?").run()
    assert not at.exception
    texts = [m.value for m in at.markdown]
    assert "Grounded answer citing [1]." in texts and "Plain answer without sources." in texts
    assert len(FakeGroq.calls) == 2
    assert any("(cited)" in t for t in texts)


def test_retrieval_only_makes_no_llm_call(app_env, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    at = run_app()
    at.sidebar.toggle[1].set_value(True).run()     # retrieval only
    at.chat_input[0].set_value("paging external fragmentation").run()
    assert not at.exception and FakeGroq.calls == []


def test_ask_shows_latest_only_and_history_keeps_all(app_env, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    at = run_app()
    at.chat_input[0].set_value("What are the conditions for deadlock?").run()
    at.chat_input[0].set_value("paging external fragmentation").run()
    assert not at.exception
    ask, history = at.tabs[0], at.tabs[1]
    ask_questions = [m.markdown[0].value for m in ask.chat_message if m.name == "user"]
    hist_questions = [m.markdown[0].value for m in history.chat_message if m.name == "user"]
    assert ask_questions == ["paging external fragmentation"]
    assert hist_questions == ["paging external fragmentation", "What are the conditions for deadlock?"]


def test_compare_tab_shows_three_methods(app_env):
    at = run_app()
    at.text_input(key="cmp_question").input("mutex lock").run()
    at.button(key="cmp_button").click().run()
    assert not at.exception
    heads = [m.value for m in at.markdown if m.value.startswith("#### ")]
    assert heads == ["#### Dense (embeddings)", "#### BM25 (keywords)", "#### Hybrid (RRF)"]


def test_dataset_tab_shows_real_stats_and_rebuild_works(app_env):
    at = run_app()
    labels = {m.label: m.value for m in at.metric}
    stats = json.loads((config.INDEX_DIR / "stats.json").read_text())
    assert labels["Chunks indexed"] == str(stats["chunks_indexed"])
    at.button(key="build_button").click().run()
    assert not at.exception


def test_evaluation_tab_empty_then_flags_standin_run(app_env):
    at = run_app()
    assert any("No evaluation has been run yet" in i.value for i in at.info)
    config.RESULTS_DIR.mkdir(parents=True)
    run = {"summary": {m: {"n": 2, "hit@3": 1, "hit@5": 2, "mrr@10": 0.75}
                       for m in ("hybrid", "dense", "bm25")},
           "by_type": {}, "per_question": {"hybrid": [], "dense": [], "bm25": []},
           "n_questions_used": 2, "unlabelled": [],
           "meta": {"reportable": False, "embedder": "hashing-standin-384", "run_at": "x"}}
    (config.RESULTS_DIR / "results_1.json").write_text(json.dumps(run))
    at = run_app()
    assert any("NOT reportable" in w.value for w in at.warning)


def test_missing_index_points_to_build_button(app_env, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path / "empty_index")
    at = run_app()
    assert any("click 'Build index'" in i.value for i in at.info)
