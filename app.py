"""BootUp demo app.   streamlit run app.py

Tabs: Ask | History | Compare retrieval | Dataset | Evaluation | How it works
Nothing on screen is invented: the Dataset and Evaluation tabs only show what
the build and evaluate scripts actually wrote to disk.
"""
import json
import os
import re
import textwrap
from pathlib import Path

import pandas as pd
import streamlit as st

from bootup import config
from bootup.build import run_build
from bootup.embed import get_embedder
from bootup.generate import (IncompleteAnswerError, MissingKeyError, extract_cited, generate_answer,
                             generate_baseline)
from bootup.index import Index
from bootup.retrieve import MODES, Retriever

st.set_page_config(page_title="BootUp", page_icon="\U0001F4BB", layout="wide")

# The Groq key may come from the environment or from .streamlit/secrets.toml.
if not os.environ.get("GROQ_API_KEY"):
    try:
        _key = st.secrets.get("GROQ_API_KEY")
    except Exception:  # no secrets file
        _key = None
    if _key:
        os.environ["GROQ_API_KEY"] = _key

METHOD_LABELS = {"dense": "Dense (embeddings)", "bm25": "BM25 (keywords)",
                 "hybrid": "Hybrid (RRF)"}

SHORT_LABELS = {"hybrid": "Hybrid", "dense": "Dense", "bm25": "BM25"}
MODE_HELP = {"hybrid": "Merges both rankings with Reciprocal Rank Fusion.",
             "dense": "Matches meaning, even when the wording differs.",
             "bm25": "Matches exact terms such as Banker's or Bakery."}

# Theme colors, fonts and the base radius come from .streamlit/config.toml. This layer adds the
# header, the segmented tab bar, cards and the answer reveal. Radius rule: controls 10px,
# panels and cards 14px. The accent is the same teal as the theme (lighter in dark mode).
st.markdown("""
<style>
:root { --bu-accent: #0F766E; --bu-on-accent: #F7FFFD; --bu-surface: #FDFDFD;
        --bu-soft: rgba(15, 118, 110, 0.08); --bu-shadow: 0 1px 2px rgba(24, 24, 27, 0.06),
        0 8px 24px -12px rgba(15, 118, 110, 0.18); }
@media (prefers-color-scheme: dark) {
  :root { --bu-accent: #2DD4BF; --bu-on-accent: #04201D; --bu-surface: #18181C;
          --bu-soft: rgba(45, 212, 191, 0.10); --bu-shadow: 0 1px 2px rgba(0, 0, 0, 0.4); }
}
[data-testid="stMainBlockContainer"] { max-width: 1120px; padding-top: 2rem; }

/* Header */
.bu-head { display: flex; align-items: center; gap: 0.9rem; margin: 0.25rem 0 1.4rem; }
.bu-mark { flex: none; width: 46px; height: 46px; border-radius: 14px; display: grid;
           place-items: center; background: var(--bu-accent); color: var(--bu-on-accent);
           font-weight: 700; font-size: 1.35rem; letter-spacing: -0.03em; }
.bu-title { font-size: 1.85rem; font-weight: 700; letter-spacing: -0.03em; line-height: 1.1; }
.bu-sub { font-size: 0.95rem; opacity: 0.68; margin-top: 0.2rem; }
.bu-meta { margin-left: auto; display: flex; gap: 0.5rem; flex-wrap: wrap; justify-content: flex-end; }
.bu-chip { font-family: "Geist Mono", monospace; font-size: 0.78rem; padding: 0.3rem 0.65rem;
           border-radius: 10px; border: 1px solid color-mix(in srgb, currentColor 14%, transparent);
           white-space: nowrap; }
.bu-chip b { color: var(--bu-accent); font-weight: 600; }
@media (max-width: 768px) { .bu-head { flex-wrap: wrap; } .bu-meta { margin-left: 0; justify-content: flex-start; } }

/* Tabs as one segmented bar */
[role="tablist"] { gap: 2px; padding: 4px; border-radius: 14px; width: fit-content; max-width: 100%;
  overflow-x: auto; border: none; background: color-mix(in srgb, currentColor 6%, transparent); }
[role="tablist"]::after, [role="tablist"]::before { display: none; }
[data-testid="stTab"] { padding: 0.45rem 0.95rem; border-radius: 10px; height: auto; border: none;
  transition: background-color 0.2s ease; }
[data-testid="stTab"][aria-selected="true"] { background: var(--bu-surface); box-shadow: var(--bu-shadow); }
[data-testid="stTab"][aria-selected="true"] p { color: var(--bu-accent); font-weight: 600; }
[data-testid="stTab"] .react-aria-SelectionIndicator { display: none; }

/* Ask panel */
.st-key-askpanel { background: var(--bu-surface); border-radius: 14px; padding: 1.4rem 1.5rem 1.2rem;
  border: 1px solid color-mix(in srgb, currentColor 10%, transparent); box-shadow: var(--bu-shadow); }
.bu-ask-title { font-size: 1.3rem; font-weight: 650; letter-spacing: -0.02em; }
.bu-ask-sub { font-size: 0.92rem; opacity: 0.68; margin-top: 0.15rem; }
.bu-label { font-size: 0.8rem; font-weight: 600; opacity: 0.6; margin-top: 0.35rem; }
.st-key-examples button { border-radius: 10px; background: transparent; }
.st-key-examples button:hover { border-color: var(--bu-accent); color: var(--bu-accent); background: var(--bu-soft); }
.st-key-examples button p { font-size: 0.88rem; font-weight: 450; }
.stButton button:active { transform: translateY(1px) scale(0.99); }

/* Answer and sources */
[data-testid="stChatMessage"] { background: var(--bu-surface); border-radius: 14px; padding: 1rem 1.1rem;
  border: 1px solid color-mix(in srgb, currentColor 9%, transparent); }
[class*="st-key-q_"] [data-testid="stChatMessage"] { background: var(--bu-soft); border-color: transparent; }
[class*="st-key-q_"] [data-testid="stChatMessage"] p { font-weight: 550; }
.st-key-latest [data-testid="stExpander"] details { border-radius: 14px; }
[class*="st-key-src_"] { background: color-mix(in srgb, currentColor 3%, transparent); border-radius: 14px; }
@media (prefers-reduced-motion: no-preference) {
  .st-key-latest { animation: bu-rise 0.35s cubic-bezier(0.16, 1, 0.3, 1) both; }
  @keyframes bu-rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
}

/* Sidebar */
.st-key-status { border-radius: 14px; padding: 0.75rem 0.9rem;
  border: 1px solid color-mix(in srgb, currentColor 10%, transparent); }
.st-key-status [data-testid="stCaptionContainer"] { margin-bottom: -0.35rem; }
</style>
""", unsafe_allow_html=True)

# Course files are named like "FALLSEM2025-26_VL_BCSE303L_00100_TH_2026-06-13_MODULE-3.pdf".
COURSE_PREFIX = re.compile(r"^(FALL|WIN)SEM\d{4}-\d{2}_VL_[A-Z0-9]+_\d+_TH_\d{4}-\d{2}-\d{2}_")


def short(text: str, width: int) -> str:
    return textwrap.shorten(" ".join(text.split()), width=width, placeholder=" ...")


TOPIC_ICONS = [("deadlock", ":material/block:"), ("bakery", ":material/sync_lock:"),
               ("critical section", ":material/sync_lock:"), ("round robin", ":material/autorenew:"),
               ("scheduling", ":material/schedule:"), ("process control", ":material/memory:"),
               ("fit", ":material/view_agenda:"), ("kernel", ":material/layers:")]


def topic_icon(question: str) -> str:
    q = question.lower()
    return next((icon for word, icon in TOPIC_ICONS if word in q), ":material/help:")


def as_markdown(answer: str) -> str:
    r"""Models often write math as \( ... \) or \[ ... \]; Streamlit renders $ ... $ and $$ ... $$."""
    answer = re.sub(r"\\\[(.+?)\\\]", r"$$\1$$", answer, flags=re.S)
    return re.sub(r"\\\((.+?)\\\)", r"$\1$", answer)


def short_name(source_file: str) -> str:
    """'course/deadlocks/WINSEM..._Module-3.pptx' -> 'Module-3.pptx'."""
    return COURSE_PREFIX.sub("", source_file.split("/")[-1])


@st.cache_resource(show_spinner="Loading the embedding model...")
def load_embedder(name: str):
    return get_embedder(name)


@st.cache_resource(show_spinner="Loading the index...")
def load_retriever(_embedder, index_dir: str, version: int):
    return Retriever(Index(Path(index_dir), _embedder), _embedder)


st.session_state.setdefault("index_version", 0)
st.session_state.setdefault("turns", [])

header = st.empty()

try:
    embedder = load_embedder(config.EMBED_MODEL)
except Exception as exc:
    st.error(f"Could not load the embedding model '{config.EMBED_MODEL}': {exc}")
    st.stop()

retriever, index_error = None, None
try:
    retriever = load_retriever(embedder, str(config.INDEX_DIR), st.session_state.index_version)
except Exception as exc:
    index_error = str(exc)

# Header chips only show numbers the build actually wrote to disk.
chips = ['<span class="bu-chip">BCSE303L Operating Systems</span>']
_stats_path = config.INDEX_DIR / "stats.json"
if _stats_path.exists():
    _course = json.loads(_stats_path.read_text()).get("files_by_source_type", {}).get("course")
    if _course:
        chips.append(f'<span class="bu-chip"><b>{_course}</b> course files</span>')
if retriever is not None:
    chips.append(f'<span class="bu-chip"><b>{retriever.index.meta["n_chunks"]}</b> chunks</span>')
header.markdown(f"""
<div class="bu-head">
  <div class="bu-mark" aria-hidden="true">B</div>
  <div>
    <div class="bu-title" role="heading" aria-level="1">BootUp</div>
    <div class="bu-sub">An Operating Systems study assistant that answers only from the loaded
      course material and shows where every answer came from.</div>
  </div>
  <div class="bu-meta">{"".join(chips)}</div>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.subheader("Settings")
    mode = st.segmented_control("Retrieval method", MODES, default=MODES[0], required=True,
                                format_func=lambda m: SHORT_LABELS[m], width="stretch",
                                help="Hybrid merges the dense and BM25 rankings with "
                                     "Reciprocal Rank Fusion.")
    st.caption(MODE_HELP[mode])
    k = st.slider("Passages sent to the model", 1, 8, config.TOP_K_FINAL)
    compare_plain = st.toggle("Compare with a plain LLM answer",
                              help="Same model, same question, but without retrieved passages.")
    retrieval_only = st.toggle("Retrieval only (skip the LLM)",
                               help="Show the matching slides and pages without calling the model.")
    with st.container(key="status"):
        st.markdown("**Status**")
        key_set = bool(os.environ.get("GROQ_API_KEY"))
        if key_set:
            st.badge("Groq key found", icon=":material/check:", color="primary")
        else:
            st.caption("Groq API key: not set (retrieval still works)")
        st.caption(f"LLM: {config.LLM_MODEL}")
        st.caption(f"Embedder: {embedder.name.split('/')[-1]}")
        if retriever is not None:
            st.caption(f"Chunks indexed: {retriever.index.meta['n_chunks']}")
    if embedder.is_standin:
        st.warning("Offline stand-in embedder: for testing the code only.")

ask_tab, hist_tab, cmp_tab, data_tab, eval_tab, how_tab = st.tabs(
    ["Ask", "History", "Compare retrieval", "Dataset", "Evaluation", "How it works"])


# --------------------------------------------------------------------- Ask
def show_sources(hits, cited, method, expanded, uid):
    with st.expander(f"Sources: {len(hits)} passages, {METHOD_LABELS[method]}",
                     expanded=expanded, icon=":material/description:"):
        if not hits:
            st.write("No passages matched.")
        for row in range(0, len(hits), 2):
            for col, i in zip(st.columns(2), range(row + 1, min(row + 3, len(hits) + 1))):
                c = hits[i - 1].chunk
                ranks = ", ".join(f"{name} #{r}" for name, r in hits[i - 1].ranks.items())
                cited_tag = " :primary[**(cited)**]" if i in cited else ""
                with col.container(border=True, key=f"src_{uid}_{i}"):
                    st.markdown(f"**[{i}]**{cited_tag} `{short_name(c.source_file)}` {c.locator}",
                                help=c.source_file)
                    st.caption(f"{c.topic} | {c.source_type} | rank: {ranks}")
                    st.caption(short(c.text, 260))


def run_turn(question: str) -> dict:
    hits = retriever.search(question, mode=mode, k_final=k)
    turn = {"question": question, "mode": mode, "hits": hits, "answer": None,
            "plain": None, "cited": [], "error": None}
    if retrieval_only:
        return turn
    try:
        turn["answer"] = generate_answer(question, hits)
        turn["cited"] = extract_cited(turn["answer"])
        if compare_plain:
            turn["plain"] = generate_baseline(question)
    except (MissingKeyError, IncompleteAnswerError) as exc:
        turn["error"] = str(exc)
    except Exception as exc:
        turn["error"] = f"The language model call failed: {exc}"
    return turn


def render_turn(turn: dict, latest: bool, uid: str) -> None:
    with st.container(key=f"q_{uid}"):
        with st.chat_message("user", avatar=":material/person:"):
            st.markdown(turn["question"])
    with st.chat_message("assistant", avatar=":material/menu_book:"):
        with st.container(horizontal=True, gap="small"):
            st.badge(SHORT_LABELS[turn["mode"]] + " search", icon=":material/search:", color="gray")
            if turn["answer"]:
                n = len(turn["cited"])
                st.badge(f"{n} source{'s' if n != 1 else ''} cited",
                         icon=":material/format_quote:", color="primary")
        if turn["plain"] is not None:
            left, right = st.columns(2)
            with left:
                st.markdown("**BootUp: answers from the course material**")
                st.markdown(as_markdown(turn["answer"]))
            with right:
                st.markdown("**Plain LLM: same model, no course material**")
                st.markdown(as_markdown(turn["plain"]))
        elif turn["answer"]:
            st.markdown(as_markdown(turn["answer"]))
        elif turn["error"]:
            st.warning(turn["error"] + "\n\nThe retrieved passages are shown below.")
        else:
            st.markdown("Retrieved passages (LLM skipped):")
        show_sources(turn["hits"], turn["cited"], turn["mode"], expanded=latest, uid=uid)


with ask_tab:
    if retriever is None:
        st.info(f"No index loaded yet ({index_error}). Open the Dataset tab and click "
                "'Build index'.")
    else:
        with st.container(key="askpanel"):
            st.markdown('<div class="bu-ask-title">Ask about your course</div>'
                        '<div class="bu-ask-sub">Answers come only from your slides and notes, '
                        'with the slide or page they came from.</div>', unsafe_allow_html=True)
            typed = st.chat_input("Ask an Operating Systems question")
            st.markdown('<div class="bu-label">Or start with one of these</div>',
                        unsafe_allow_html=True)
            with st.container(key="examples", horizontal=True, wrap=True, gap="small"):
                for i, q in enumerate(config.DEMO_QUESTIONS):
                    if st.button(q, key=f"example_{i}", icon=topic_icon(q), width="content"):
                        st.session_state.pending = q

        # Only the latest question and answer are shown here; earlier ones live in History.
        question = typed or st.session_state.pop("pending", None)
        if question:
            with st.spinner("Searching your course material and writing the answer..."):
                st.session_state.turns.append(run_turn(question))
        if st.session_state.turns:
            with st.container(key="latest"):
                render_turn(st.session_state.turns[-1], latest=True, uid="ask")

# ------------------------------------------------------------------ History
with hist_tab:
    turns = st.session_state.turns
    if not turns:
        st.info("No questions asked yet. Questions you ask in the Ask tab are listed here, "
                "newest first.")
    else:
        st.caption(f"{len(turns)} question(s) this session, newest first.")
        if st.button("Clear history", key="clear_history"):
            st.session_state.turns = []
            st.rerun()
        for n, t in zip(range(len(turns), 0, -1), reversed(turns)):
            st.markdown(f"**Q{n}**")
            render_turn(t, latest=False, uid=f"h{n}")

# --------------------------------------------------------- Compare retrieval
with cmp_tab:
    st.markdown("The same question searched three ways, top 5 each. Passages that appear in "
                "both the dense and the BM25 list are marked **both**. Keyword-heavy questions "
                "(a function name, a flag, an error code) are where the methods tend to differ.")
    if retriever is None:
        st.info("Build the index first (Dataset tab).")
    else:
        cq = st.text_input("Question", key="cmp_question",
                           placeholder="e.g. Bakery algorithm ticket number")
        if st.button("Compare methods", key="cmp_button") and cq.strip():
            st.session_state.cmp = {"question": cq,
                                    "results": {m: retriever.search(cq, mode=m, k_final=5)
                                                for m in MODES}}
        res = st.session_state.get("cmp")
        if res:
            r = res["results"]
            dense_ids = {h.chunk.id for h in r["dense"]}
            bm25_ids = {h.chunk.id for h in r["bm25"]}
            shared = len(dense_ids & bm25_ids)
            st.caption(f"Question: {res['question']}  |  {shared} passage(s) shared by dense "
                       "and BM25 top 5")
            for col, m in zip(st.columns(3), ("dense", "bm25", "hybrid")):
                with col:
                    st.markdown(f"#### {METHOD_LABELS[m]}")
                    if not r[m]:
                        st.write("No matches.")
                    for i, h in enumerate(r[m], 1):
                        c = h.chunk
                        both = " | **both**" if c.id in dense_ids and c.id in bm25_ids else ""
                        st.markdown(f"**{i}.** `{short_name(c.source_file)}` | {c.locator}{both}",
                                    help=c.source_file)
                        st.caption(short(c.text, 200))

# ------------------------------------------------------------------ Dataset
with data_tab:
    stats_path = config.INDEX_DIR / "stats.json"
    if stats_path.exists():
        stats = json.loads(stats_path.read_text())
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Files used", stats["files_used"], border=True)
        m2.metric("Chunks indexed", stats.get("chunks_indexed", "-"), border=True)
        m3.metric("Near-duplicates dropped", stats["duplicates_dropped"], border=True)
        m4.metric("Mean words per chunk", stats["words_per_chunk"]["mean"], border=True)
        st.caption(f"Built {stats.get('built_at', '')} with {stats.get('embedder', '')}. "
                   f"Max words per chunk: {stats['words_per_chunk']['max']}.")
        c1, c2 = st.columns(2)
        c1.markdown("**Chunks by source type**")
        c1.dataframe(pd.DataFrame(sorted(stats["chunks_by_source_type"].items()),
                                  columns=["source type", "chunks"]), hide_index=True)
        c2.markdown("**Chunks by topic**")
        c2.dataframe(pd.DataFrame(sorted(stats["chunks_by_topic"].items()),
                                  columns=["topic", "chunks"]), hide_index=True)
        if stats["files_skipped"]:
            st.warning("Skipped files:\n" + "\n".join(
                f"- {s['file']}: {s['reason']}" for s in stats["files_skipped"]))
    else:
        st.info("No statistics yet. Build the index below.")

    if retriever is not None:
        st.markdown("**Browse chunks**")
        files = sorted({c.source_file for c in retriever.index.chunk_list})
        chosen = st.selectbox("File", files, key="browse_file")
        file_chunks = [c for c in retriever.index.chunk_list if c.source_file == chosen]
        st.caption(f"{len(file_chunks)} chunks from this file")
        for c in file_chunks[:30]:
            with st.expander(f"{c.locator} | {len(c.text.split())} words"):
                st.text(c.text)

    st.divider()
    st.markdown(f"**Build index** from the files in `{config.DATA_DIR}`. Do this after adding "
                "or removing files. The first build downloads the embedding model.")
    if st.button("Build index", key="build_button"):
        with st.spinner("Reading files, chunking, embedding and indexing..."):
            try:
                built = run_build(config.DATA_DIR, config.INDEX_DIR, embedder)
            except Exception as exc:
                st.error(f"Build failed: {exc}")
            else:
                st.session_state.index_version += 1
                st.session_state.pop("cmp", None)
                st.success(f"Indexed {built['chunks_indexed']} chunks from "
                           f"{built['files_used']} files.")
                st.rerun()

# --------------------------------------------------------------- Evaluation
with eval_tab:
    runs = sorted(config.RESULTS_DIR.glob("results_*.json")) if config.RESULTS_DIR.exists() else []
    if not runs:
        st.info("No evaluation has been run yet. Write 15-20 labelled questions in "
                "eval/questions.json (template: eval/questions.template.json), then run "
                "`python -m bootup.evaluate`. Results appear here.")
    else:
        pick = st.selectbox("Evaluation run", [p.name for p in reversed(runs)])
        res = json.loads((config.RESULTS_DIR / pick).read_text())
        meta = res.get("meta", {})
        if not meta.get("reportable", False):
            st.warning("This run used the offline stand-in embedder. Its numbers are NOT "
                       "reportable.")
        n = res["n_questions_used"]
        st.caption(f"Run at {meta.get('run_at', '?')} | embedder {meta.get('embedder', '?')} | "
                   f"{n} questions")
        rows = [{"method": METHOD_LABELS[m], "hit@3": f"{s['hit@3']}/{s['n']}",
                 "hit@5": f"{s['hit@5']}/{s['n']}", "MRR@10": f"{s['mrr@10']:.3f}"}
                for m, s in res["summary"].items()]
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        if res.get("by_type"):
            st.markdown("**hit@5 by question type**")
            type_rows = [{"type": t, **{METHOD_LABELS[m]: f"{s['hit@5']}/{s['n']}"
                                        for m, s in per.items()}}
                         for t, per in res["by_type"].items()]
            st.dataframe(pd.DataFrame(type_rows), hide_index=True)
        per_q = {}
        for m, rows_m in res["per_question"].items():
            for row in rows_m:
                per_q.setdefault(row["id"], {"question": row["id"], "type": row["type"]})
                per_q[row["id"]][METHOD_LABELS[m]] = row["rank"] if row["rank"] else "-"
        with st.expander("Rank of the first correct passage, per question"):
            st.dataframe(pd.DataFrame(list(per_q.values())), hide_index=True)
        if res.get("unlabelled"):
            st.caption("Left out (labels matched no chunk): " + ", ".join(res["unlabelled"]))
        st.caption(f"With {n} questions, a difference of one or two questions between methods "
                   "is not strong evidence either way.")

# ------------------------------------------------------------- How it works
with how_tab:
    st.markdown(f"""
**Offline (when the index is built)**
1. Read slides, PDFs (including the textbook chapters), Word files, text files and the question-answer bank from `data/raw/`.
2. Clean the text: drop page numbers and repeated headers, join hyphenated line breaks.
3. Split each source type by its own rule: slides per slide, running text
   into sentence-aligned chunks of about {config.CHUNK_TOKENS} tokens with about
   {int(config.OVERLAP_FRACTION * 100)}% overlap, Q&A pairs kept whole.
4. Tag every chunk with its file, source type, topic and page or slide.
5. Embed each chunk ({embedder.name}), drop near-duplicates, store in ChromaDB, and build a
   BM25 keyword index over the same chunks.

**At question time**
1. Search both indexes: top {config.TOP_K_EACH} from each.
2. Merge with Reciprocal Rank Fusion: score = sum of 1 / ({config.RRF_K} + rank).
3. Send the best passages to {config.LLM_MODEL} with instructions to answer only from them and
   cite them as [1], [2].
4. Show the answer with its sources and their ranks in each method.
""")
