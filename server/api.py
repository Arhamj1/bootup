"""BootUp HTTP API for the React frontend.   python -m server   (or run_app.bat)

Same pipeline as the Streamlit app (bootup/), exposed as JSON endpoints. /api/ask streams the
answer as server-sent events: one "sources" event, then "token" events, then "done".
Nothing here invents data: stats and evaluation results are read from what the build and
evaluate scripts wrote to disk.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import threading
import time
import tomllib
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from bootup import config
from bootup.build import run_build
from bootup.embed import get_embedder
from bootup.generate import (IncompleteAnswerError, MissingKeyError, extract_cited, stream_answer,
                             stream_baseline)
from bootup.index import Index
from bootup.retrieve import MODES, Retriever

COURSE_NAME = "BCSE303L Operating Systems"
FRONTEND_DIST = config.ROOT / "frontend" / "dist"
# Course files are named like "FALLSEM2025-26_VL_BCSE303L_00100_TH_2026-06-13_MODULE-3.pdf".
COURSE_PREFIX = re.compile(r"^(FALL|WIN)SEM\d{4}-\d{2}_VL_[A-Z0-9]+_\d+_TH_\d{4}-\d{2}-\d{2}_")

# --- public deployment (Hugging Face Space). All off unless the variables are set. -----------
# BOOTUP_ACCESS_CODE  every /api call except /api/status must send it in the X-Access-Code header
# BOOTUP_PUBLIC=1     disables rebuilding the index from the browser
# BOOTUP_RATE_PER_MIN questions allowed per visitor per minute (0 = no limit)
# BOOTUP_INDEX_REPO   private Hugging Face dataset holding index/, downloaded at start (uses HF_TOKEN)
ACCESS_CODE = os.getenv("BOOTUP_ACCESS_CODE") or None
PUBLIC = os.getenv("BOOTUP_PUBLIC") == "1"
RATE_PER_MIN = int(os.getenv("BOOTUP_RATE_PER_MIN", "12" if PUBLIC else "0"))


def fetch_index_from_hub() -> None:
    """On the Space the index is not in the image; pull it from a private dataset once."""
    repo = os.getenv("BOOTUP_INDEX_REPO")
    if not repo or (config.INDEX_DIR / "meta.json").exists():
        return
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=repo, repo_type="dataset", local_dir=str(config.INDEX_DIR),
                      token=os.getenv("HF_TOKEN"))


def use_cached_model_offline() -> None:
    """If the embedding model is already downloaded, skip Hugging Face's online update check.
    That check is what makes start-up slow (and fail without internet)."""
    if "HF_HUB_OFFLINE" in os.environ:
        return
    try:
        from huggingface_hub import try_to_load_from_cache
        if isinstance(try_to_load_from_cache(config.EMBED_MODEL, "config.json"), str):
            os.environ["HF_HUB_OFFLINE"] = "1"
            import huggingface_hub.constants as hf_constants  # already imported above: set it too
            hf_constants.HF_HUB_OFFLINE = True
    except Exception:
        pass  # stand-in embedder, or huggingface_hub missing: leave the default behaviour


def load_groq_key() -> None:
    """Use GROQ_API_KEY from the environment, else from .streamlit/secrets.toml (same as the app)."""
    if os.environ.get("GROQ_API_KEY"):
        return
    secrets = config.ROOT / ".streamlit" / "secrets.toml"
    if secrets.exists():
        try:
            key = tomllib.loads(secrets.read_text(encoding="utf-8")).get("GROQ_API_KEY")
        except tomllib.TOMLDecodeError:
            key = None
        if key:
            os.environ["GROQ_API_KEY"] = key


class State:
    """Embedder and retriever, loaded once and swapped after a rebuild."""

    def __init__(self):
        self.lock = threading.Lock()
        self.embedder = None
        self.retriever = None
        self.index_error: str | None = None

    def get_embedder(self):
        with self.lock:
            if self.embedder is None:
                self.embedder = get_embedder(config.EMBED_MODEL)
            return self.embedder

    def get_retriever(self) -> Retriever:
        emb = self.get_embedder()
        with self.lock:
            if self.retriever is None:
                try:
                    self.retriever = Retriever(Index(config.INDEX_DIR, emb), emb)
                    self.index_error = None
                except Exception as exc:  # no index built yet, or embedder mismatch
                    self.index_error = str(exc)
                    raise HTTPException(409, f"No index loaded ({exc}). Build the index first.")
            return self.retriever

    def reset(self):
        with self.lock:
            self.retriever = None


state = State()


# ------------------------------------------------------------------ helpers
def short_name(source_file: str) -> str:
    return COURSE_PREFIX.sub("", source_file.split("/")[-1])


def hit_json(n: int, hit) -> dict:
    c = hit.chunk
    return {"n": n, "id": c.id, "file": c.source_file, "name": short_name(c.source_file),
            "locator": c.locator, "topic": c.topic, "source_type": c.source_type,
            "ranks": hit.ranks, "score": round(hit.score, 5), "text": c.text}


def read_stats() -> dict | None:
    path = config.INDEX_DIR / "stats.json"
    return json.loads(path.read_text()) if path.exists() else None


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------- app
@asynccontextmanager
async def lifespan(_app):
    # Load the embedding model and index in the background so the first page load is quick.
    def warm():
        try:
            state.get_retriever()
        except Exception:
            pass  # reported by /api/status instead
    threading.Thread(target=warm, daemon=True).start()
    yield


app = FastAPI(title="BootUp API", lifespan=lifespan)
load_groq_key()
INDEX_FETCH_ERROR: str | None = None
try:
    fetch_index_from_hub()  # before offline mode is switched on below
except Exception as exc:
    INDEX_FETCH_ERROR = f"Could not download the index from {os.getenv('BOOTUP_INDEX_REPO')}: {exc}"
use_cached_model_offline()


def code_ok(request: Request) -> bool:
    if not ACCESS_CODE:
        return True
    return hmac.compare_digest(request.headers.get("x-access-code", ""), ACCESS_CODE)


@app.middleware("http")
async def require_access_code(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path != "/api/status" and not code_ok(request):
        return JSONResponse({"detail": "Access code required."}, status_code=401)
    return await call_next(request)


_recent: dict[str, deque] = defaultdict(deque)
_recent_lock = threading.Lock()


def check_rate(request: Request) -> None:
    """At most RATE_PER_MIN questions per visitor per rolling minute (keeps the Groq quota safe)."""
    if RATE_PER_MIN <= 0:
        return
    forwarded = request.headers.get("x-forwarded-for", "")
    who = forwarded.split(",")[0].strip() or (request.client.host if request.client else "?")
    now = time.monotonic()
    with _recent_lock:
        q = _recent[who]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_PER_MIN:
            raise HTTPException(429, "Too many questions in the last minute. Wait a moment and try again.")
        q.append(now)


@app.get("/api/status")
def status(request: Request, wait: bool = False):
    """Answers at once; "loading" is true while the model and index are still being loaded.
    Without the access code it only says that one is needed."""
    authorized = code_ok(request)
    if not authorized:
        return {"auth_required": True, "authorized": False, "public": PUBLIC, "course": COURSE_NAME}
    stats = read_stats() or {}
    emb, retriever = state.embedder, state.retriever
    if wait or (emb is not None and retriever is None and state.index_error is None):
        try:
            retriever = state.get_retriever()
        except HTTPException:
            pass
        emb = state.embedder
    return {
        "auth_required": bool(ACCESS_CODE),
        "authorized": True,
        "public": PUBLIC,
        "loading": INDEX_FETCH_ERROR is None and (emb is None or (retriever is None and state.index_error is None)),
        "course": COURSE_NAME,
        "key_set": bool(os.environ.get("GROQ_API_KEY")),
        "llm_model": config.LLM_MODEL,
        "embedder": emb.name if emb else config.EMBED_MODEL,
        "embedder_is_standin": bool(emb and emb.is_standin),
        "chunks": retriever.index.meta["n_chunks"] if retriever else None,
        "course_files": stats.get("files_by_source_type", {}).get("course"),
        "index_error": INDEX_FETCH_ERROR or state.index_error,
        "examples": config.DEMO_QUESTIONS,
        "modes": list(MODES),
        "default_k": config.TOP_K_FINAL,
        "settings": {"chunk_tokens": config.CHUNK_TOKENS,
                     "overlap_pct": int(config.OVERLAP_FRACTION * 100),
                     "top_k_each": config.TOP_K_EACH, "top_k_final": config.TOP_K_FINAL,
                     "rrf_k": config.RRF_K},
    }


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: str = "hybrid"
    k: int = Field(default=config.TOP_K_FINAL, ge=1, le=8)
    compare_plain: bool = False
    retrieval_only: bool = False


@app.post("/api/ask")
def ask(req: AskRequest, request: Request):
    if req.mode not in MODES:
        raise HTTPException(422, f"mode must be one of {MODES}")
    check_rate(request)
    retriever = state.get_retriever()
    hits = retriever.search(req.question, mode=req.mode, k_final=req.k)

    def events():
        yield sse("sources", {"mode": req.mode, "hits": [hit_json(i, h) for i, h in enumerate(hits, 1)]})
        if req.retrieval_only:
            yield sse("done", {"cited": [], "skipped": True})
            return
        answer = ""
        try:
            for piece in stream_answer(req.question, hits):
                answer += piece
                yield sse("token", {"t": piece})
            if req.compare_plain:
                for piece in stream_baseline(req.question):
                    yield sse("plain", {"t": piece})
        except (MissingKeyError, IncompleteAnswerError) as exc:
            yield sse("error", {"message": str(exc)})
        except Exception as exc:
            yield sse("error", {"message": f"The language model call failed: {exc}"})
        yield sse("done", {"cited": extract_cited(answer)})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/compare")
def compare(q: str):
    if not q.strip():
        raise HTTPException(422, "Empty question")
    retriever = state.get_retriever()
    results = {m: [hit_json(i, h) for i, h in enumerate(retriever.search(q, mode=m, k_final=5), 1)]
               for m in MODES}
    shared = {h["id"] for h in results["dense"]} & {h["id"] for h in results["bm25"]}
    return {"question": q, "results": results, "shared": sorted(shared)}


@app.get("/api/stats")
def stats():
    data = read_stats()
    if data is None:
        raise HTTPException(404, "No statistics yet. Build the index first.")
    return data


@app.get("/api/files")
def files():
    chunks = state.get_retriever().index.chunk_list
    counts: dict[str, int] = {}
    for c in chunks:
        counts[c.source_file] = counts.get(c.source_file, 0) + 1
    return [{"file": f, "name": short_name(f), "chunks": n} for f, n in sorted(counts.items())]


@app.get("/api/chunks")
def chunks(file: str):
    rows = [c for c in state.get_retriever().index.chunk_list if c.source_file == file]
    if not rows:
        raise HTTPException(404, "No chunks for that file")
    return [{"locator": c.locator, "words": len(c.text.split()), "text": c.text} for c in rows[:40]]


@app.post("/api/build")
def build():
    if PUBLIC:
        raise HTTPException(403, "Rebuilding the index is disabled on the public site.")
    emb = state.get_embedder()
    try:
        built = run_build(config.DATA_DIR, config.INDEX_DIR, emb)
    except Exception as exc:
        raise HTTPException(500, f"Build failed: {exc}")
    state.reset()
    return {"chunks_indexed": built["chunks_indexed"], "files_used": built["files_used"]}


@app.get("/api/eval")
def eval_runs():
    runs = sorted(config.RESULTS_DIR.glob("results_*.json")) if config.RESULTS_DIR.exists() else []
    return {"runs": [p.name for p in reversed(runs)]}


@app.get("/api/eval/{name}")
def eval_run(name: str):
    # Only plain file names of saved runs; no paths.
    if not re.fullmatch(r"results_[\w.-]+\.json", name):
        raise HTTPException(404, "Unknown run")
    path = config.RESULTS_DIR / name
    if not path.exists():
        raise HTTPException(404, "Unknown run")
    return json.loads(path.read_text())


# ------------------------------------------------------- built frontend (optional)
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):  # unknown API route: a real 404, not the app page
            raise HTTPException(404, "Not found")
        target = (FRONTEND_DIST / path).resolve()
        if path and target.is_file() and FRONTEND_DIST.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
