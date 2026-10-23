import json
from types import SimpleNamespace

import pytest

from bootup.embed import HashingEmbedder
from bootup.evaluate import (evaluate, find_leaks, first_relevant_rank, hit_at_k, load_questions,
                             reciprocal_rank)
from bootup.generate import (NO_CONTEXT, MissingKeyError, build_messages, expand_query, extract_cited,
                             generate_answer, make_client, search_query)
from bootup.index import Index, build_index
from bootup.ingest import Chunk, ingest_all
from bootup.retrieve import Hit, Retriever


def _hit(i):
    return Hit(Chunk(f"id{i}", f"text {i}", f"file{i}.pdf", "course", "topic", f"p.{i}"), 1.0)


def test_prompt_contains_numbered_context_and_rules():
    msgs = build_messages("What is a deadlock?", [_hit(1), _hit(2)])
    system, user = msgs[0]["content"], msgs[1]["content"]
    assert "main source" in system and "[1]" in system and "(general knowledge)" in system
    assert "[1] (source: file1.pdf, p.1" in user and "[2]" in user
    assert user.endswith("Question: What is a deadlock?")


def test_extract_cited_orders_and_dedupes():
    assert extract_cited("Yes [2]. Also see [1] and again [2], [10].") == [2, 1, 10]


def _client_replying(text=None, error=None):
    def create(**kw):
        if error:
            raise error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_expand_query_returns_one_line_of_terms():
    terms = expand_query("why does one long job hold everyone up?", client=_client_replying("convoy effect,\n FCFS"))
    assert terms == "convoy effect, FCFS"
    assert search_query("q", terms) == "q\nconvoy effect, FCFS"


def test_expand_query_never_breaks_the_answer(monkeypatch):
    assert expand_query("q", client=_client_replying(error=RuntimeError("rate limited"))) == ""
    assert expand_query("q", client=_client_replying(text=None)) == ""
    assert search_query("q", "") == "q"
    from bootup import config
    monkeypatch.setattr(config, "QUERY_EXPANSION", False)
    assert expand_query("q", client=_client_replying("terms")) == ""


def test_extract_cited_accepts_full_width_brackets():
    assert extract_cited("Circular wait 【1】, see also 【3†L4-L9】 and [1].") == [1, 3]


def test_missing_key_gives_clear_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(MissingKeyError, match="GROQ_API_KEY"):
        make_client()


def test_generate_uses_client_and_skips_call_without_context():
    calls = []

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    calls.append(kw)
                    return SimpleNamespace(choices=[SimpleNamespace(
                        message=SimpleNamespace(content="  Answer [1]  "))])

    assert generate_answer("q", [_hit(1)], client=FakeClient()) == "Answer [1]"
    assert calls[0]["temperature"] == 0.2 and calls[0]["messages"][0]["role"] == "system"
    assert generate_answer("q", [], client=FakeClient()) == NO_CONTEXT
    assert len(calls) == 1


def test_metric_functions():
    assert first_relevant_rank(["a", "b", "c"], {"c", "x"}) == 3
    assert first_relevant_rank(["a"], {"z"}) is None
    assert hit_at_k(3, 3) and not hit_at_k(4, 3) and not hit_at_k(None, 5)
    assert reciprocal_rank(4) == 0.25 and reciprocal_rank(None) == 0.0 and reciprocal_rank(11) == 0.0


def test_question_validation(tmp_path):
    p = tmp_path / "q.json"
    p.write_text(json.dumps([{"id": "a", "question": "x", "type": "concept"}]))
    with pytest.raises(ValueError, match="evidence_any"):
        load_questions(p)
    p.write_text(json.dumps([{"id": "a", "question": "x", "type": "weird", "evidence_any": ["y"]}]))
    with pytest.raises(ValueError, match="type"):
        load_questions(p)


@pytest.fixture
def retriever(corpus, tmp_path):
    chunks, _, _ = ingest_all(corpus)
    emb = HashingEmbedder()
    build_index(chunks, emb, tmp_path / "index")
    return Retriever(Index(tmp_path / "index", emb), emb)


def test_evaluate_end_to_end(retriever):
    qs = [
        {"id": "q1", "type": "keyword", "question": "steps of the banker's algorithm safety check",
         "evidence_any": ["safety algorithm sets Work"]},
        {"id": "q2", "type": "concept", "question": "why does paging avoid external fragmentation",
         "evidence_any": ["avoids external fragmentation"]},
        {"id": "q3", "type": "concept", "question": "anything",
         "evidence_any": ["this phrase is in no chunk"]},
    ]
    res = evaluate(retriever, qs)
    assert res["n_questions_used"] == 2 and res["unlabelled"] == ["q3"]
    for mode in ("dense", "bm25", "hybrid"):
        assert res["summary"][mode]["n"] == 2
        assert res["summary"][mode]["hit@5"] == 2       # easy questions on a tiny corpus
    assert set(res["by_type"]) == {"keyword", "concept"}


def test_leak_check_flags_question_copied_into_index(retriever):
    qs = [{"id": "q9", "type": "exam", "question": "What are the four conditions for deadlock?",
           "evidence_any": ["circular wait"]}]
    assert any("q9" in w for w in find_leaks(qs, retriever.index))
    clean = [{"id": "q8", "type": "exam", "question": "unrelated wording here",
              "evidence_any": ["circular wait"]}]
    assert find_leaks(clean, retriever.index) == []
