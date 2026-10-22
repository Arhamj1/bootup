# BootUp

A retrieval-grounded study assistant for Operating Systems. It answers only from the course material it
is given (lecture slides, notes and textbook chapters) and shows the slide or page each answer came from.

Arham Jain (24BDS0366), BCSE303P Operating Systems Lab, VIT Vellore.

    question -> dense search (all-MiniLM-L6-v2 embeddings) --\
                                                              >-- Reciprocal Rank Fusion -> top 4 passages -> openai/gpt-oss-20b (Groq) -> answer + sources
             -> keyword search (BM25) ----------------------- /

## What is in this repository

| Path | What it is |
|---|---|
| `bootup/` | The pipeline: ingestion and cleaning, chunking, indexing, dense/BM25/hybrid retrieval, answer generation, evaluation |
| `server/` | FastAPI backend: `/api/ask` streams the answer as server-sent events (sources, tokens, done) |
| `frontend/src/` | React web app (Vite, TypeScript, Tailwind CSS). `frontend/dist/` is the built version the server serves |
| `app.py` | The first version of the interface, in Streamlit, kept as a fallback |
| `tests/` | 58 automated tests (pytest) on a small synthetic corpus |
| `tools/` | `build_space.py` assembles deployment folders from an allow-list; `export_man_pages.py` exported the original man-page corpus |
| `deploy/render/` | Render deployment (light runtime: ONNX embeddings, NumPy vector search) |
| `deploy/space/` | Docker files for a Hugging Face Space (not used: Docker Spaces need a paid plan) |
| `render.yaml` | Render Blueprint for the public site |
| `eval/questions.template.json` | Template for the hand-labelled evaluation set |

**Not in this repository:** the course slides and notes, the textbook, the past papers and the questions
transcribed from them, the search index, and any API keys. The course material is copyrighted; the public
site loads its index from a private dataset and asks visitors for an access code.

## Running it locally

Needs Python 3.11 or 3.12 and a free Groq API key. Put course files under `data/raw/course/<topic>/`
(see `data/raw/README.md`), then:

    python -m venv .venv
    .venv\Scripts\activate                 (Windows)  |  source .venv/bin/activate  (Mac/Linux)
    pip install -r requirements.txt
    python -m bootup.build                 build the index and print dataset statistics
    python -m server                       web app at http://127.0.0.1:8000 (needs frontend/dist)

The Groq key is read from the `GROQ_API_KEY` environment variable or from `.streamlit/secrets.toml`
(`GROQ_API_KEY = "..."`, never committed). On Windows, `run_app.bat` does all of this, and
`run_demo.bat` starts the Streamlit version.

Other commands:

    python -m bootup.ask "What are the four conditions for deadlock?"        answer with sources
    python -m bootup.ask "..." --mode bm25 --no-llm                          retrieval only, no key needed
    python -m bootup.evaluate                                                three-way retrieval comparison
    python -m pytest                                                         58 tests
    cd frontend && npm install && npm run dev                                frontend with live reload (API on :8000)

## How it works

1. **Ingestion.** Slides are read per slide, PDFs per page. Running headers, page numbers and hyphenated
   line breaks are cleaned up; PDF pages whose words come out glued together are re-extracted in layout mode.
2. **Chunking.** Running text is packed into chunks of at most 150 words (about 200 tokens) with about 15%
   sentence overlap; short consecutive slides are merged. Each chunk keeps its file, topic and page or slide.
3. **Indexing.** Chunks are embedded with all-MiniLM-L6-v2 and stored in ChromaDB (also saved as a NumPy
   array); a BM25 index is built over the same chunks. Near-duplicates (cosine similarity 0.95 or more) are dropped.
4. **Retrieval.** Dense and BM25 search each return their top 10; Reciprocal Rank Fusion (1 / (60 + rank))
   merges them and the best 4 are kept.
5. **Generation.** The 4 passages go to openai/gpt-oss-20b through Groq with instructions to answer only
   from them and cite them as [1], [2].

## Results so far

On the 116 questions transcribed from 12 past papers (not included here), a retrieved passage was counted
correct if it came from the question's syllabus topic:

| Method | hit@1 | hit@4 | hit@10 | MRR@10 |
|---|---|---|---|---|
| Dense | 95/116 | 111/116 | 115/116 | 0.882 |
| BM25 | 97/116 | 110/116 | 112/116 | 0.886 |
| Hybrid (RRF) | 99/116 | 110/116 | 113/116 | 0.900 |

This is a topic-level check, not passage-level accuracy, and the differences between methods (1 to 4
questions) are too small to call one method better. The passage-level evaluation with hand-labelled
questions (`python -m bootup.evaluate`) has not been run yet.

## Settings (`bootup/config.py`)

| Setting | Default | Notes |
|---|---|---|
| CHUNK_TOKENS | 200 | Converted to words at 0.75 words per token. The embedding model ignores input past 256 tokens |
| OVERLAP_FRACTION | 0.15 | Whole sentences are carried over |
| TOP_K_EACH / TOP_K_FINAL | 10 / 4 | Per retriever before fusion / passages sent to the model |
| RRF_K | 60 | Standard smoothing constant |
| LLM_MODEL | openai/gpt-oss-20b | Override with `BOOTUP_LLM_MODEL`; use a model your Groq key can access |
| MAX_ANSWER_TOKENS / REASONING_EFFORT | 2048 / low | The budget includes the reasoning model's hidden reasoning |

## Known limits

- Answers depend on a hosted API (internet needed, free-tier rate limits).
- The model is told to answer only from the passages, but that is an instruction, not a guarantee: check the citations.
- Scanned PDFs have no text layer and are skipped; there is no OCR.
- Sentence splitting is a simple regex; abbreviations such as "e.g." can split a sentence early.
