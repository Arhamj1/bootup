import numpy as np
import pytest

from bootup.embed import HashingEmbedder, get_embedder
from bootup.index import Index, build_index, dedupe
from bootup.ingest import Chunk, ingest_all
from bootup.retrieve import Retriever, rrf_fuse
from bootup.textutil import tokenize


def test_rrf_matches_hand_calculation():
    fused = dict(rrf_fuse([["a", "b"], ["b", "c"]], k=60))
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert fused["a"] == pytest.approx(1 / 61)
    assert fused["c"] == pytest.approx(1 / 62)
    assert [d for d, _ in rrf_fuse([["a", "b"], ["b", "c"]])] == ["b", "a", "c"]


def test_tokenizer_splits_identifiers_and_drops_stopwords():
    toks = tokenize("What is the banker's algorithm? pthread_mutex_lock")
    assert "banker" in toks and "algorithm" in toks
    assert "pthread_mutex_lock" in toks and "mutex" in toks
    assert "the" not in toks and "what" not in toks


def test_get_embedder_has_no_silent_fallback():
    with pytest.raises(Exception):
        get_embedder("definitely/not-a-real-model-name")


def test_dedupe_prefers_course_over_open():
    v = np.array([[1, 0], [1, 0], [0, 1]], dtype=np.float32)
    chunks = [Chunk("open1", "x", "f", "open", "t", "l"),
              Chunk("course1", "x", "f", "course", "t", "l"),
              Chunk("other", "y", "f", "open", "t", "l")]
    keep, dropped = dedupe(chunks, v, 0.95)
    assert [chunks[i].id for i in keep] == ["course1", "other"]
    assert dropped == [("open1", "course1")]


@pytest.fixture
def retriever(corpus, tmp_path):
    chunks, _, _ = ingest_all(corpus)
    emb = HashingEmbedder()
    build_index(chunks, emb, tmp_path / "index")
    return Retriever(Index(tmp_path / "index", emb), emb)


def test_index_roundtrip_and_metadata(retriever):
    meta = retriever.index.meta
    assert meta["standin"] is True and meta["n_chunks"] == len(retriever.index.chunk_list)
    assert retriever.index.col.count() == meta["n_chunks"]


def test_index_refuses_mismatched_embedder(corpus, tmp_path):
    chunks, _, _ = ingest_all(corpus)
    build_index(chunks, HashingEmbedder(), tmp_path / "index")

    class Other(HashingEmbedder):
        name = "some-other-model"
    with pytest.raises(RuntimeError, match="Rebuild"):
        Index(tmp_path / "index", Other())


def test_bm25_finds_exact_algorithm_name(retriever):
    hits = retriever.search("banker's algorithm safety", mode="bm25", k_final=3)
    assert "banker's algorithm" in hits[0].chunk.text


def test_bm25_finds_split_identifier(retriever):
    hits = retriever.search("mutex lock", mode="bm25", k_final=3)
    assert any(h.chunk.source_file.endswith("pthread_mutex_lock.txt") for h in hits)


def test_hybrid_reports_both_ranks_and_merges_lists(retriever):
    hits = retriever.search("deadlock conditions hold and wait", mode="hybrid", k_final=5)
    assert hits and all(set(h.ranks) <= {"dense", "bm25"} for h in hits)
    assert any(len(h.ranks) == 2 for h in hits)
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_bm25_returns_nothing_for_unknown_words(retriever):
    assert retriever.search("zzzz qqqq", mode="bm25") == []


def test_invalid_mode_rejected(retriever):
    with pytest.raises(ValueError):
        retriever.search("x", mode="magic")


def test_sentence_transformer_wrapper_calls_library_correctly(monkeypatch):
    """Checks the wrapper against a fake model, so the test needs no download."""
    import sentence_transformers

    seen = {}

    class FakeModel:
        def __init__(self, name):
            seen["name"] = name

        def get_sentence_embedding_dimension(self):
            return 3

        def encode(self, texts, normalize_embeddings, show_progress_bar, batch_size):
            seen["normalize"] = normalize_embeddings
            return np.ones((len(texts), 3), dtype=np.float64)

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", FakeModel)
    emb = get_embedder("sentence-transformers/all-MiniLM-L6-v2")
    out = emb.encode(["a", "b"])
    assert seen == {"name": "sentence-transformers/all-MiniLM-L6-v2", "normalize": True}
    assert out.shape == (2, 3) and out.dtype == np.float32
    assert emb.is_standin is False and emb.dim == 3
