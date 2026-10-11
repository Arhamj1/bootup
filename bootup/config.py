"""All tunable settings in one place.

Change values here (or override the paths / model names with environment
variables) instead of hunting through the code.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- models -----------------------------------------------------------------
EMBED_MODEL = os.getenv("BOOTUP_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
LLM_MODEL = os.getenv("BOOTUP_LLM_MODEL", "openai/gpt-oss-20b")

# --- chunking ---------------------------------------------------------------
# Sizes are approximate: tokens are converted to words with WORDS_PER_TOKEN.
# all-MiniLM-L6-v2 ignores input beyond 256 tokens, so stay well below that.
CHUNK_TOKENS = 200
WORDS_PER_TOKEN = 0.75
OVERLAP_FRACTION = 0.15
MIN_MERGE_WORDS = 40        # consecutive slides shorter than this get merged
DEDUPE_THRESHOLD = 0.95     # cosine similarity above which chunks count as duplicates

# --- retrieval --------------------------------------------------------------
TOP_K_EACH = 10             # chunks taken from each retriever before fusion
TOP_K_FINAL = 4             # chunks passed to the LLM after fusion
RRF_K = 60

# --- generation -------------------------------------------------------------
TEMPERATURE = 0.2
# For reasoning models (gpt-oss) this budget also covers the hidden reasoning, which can use
# several hundred tokens on calculation questions before any answer text is written.
MAX_ANSWER_TOKENS = 2048
REASONING_EFFORT = "low"                 # "low" | "medium" | "high"; only sent to reasoning models
REASONING_MODEL_PREFIXES = ("openai/gpt-oss",)

# --- demo ---------------------------------------------------------------------
# Clickable example questions in the app, taken from the course slides; each one is
# answered from data/raw/course/.
DEMO_QUESTIONS = [
    "What are the four necessary conditions for a deadlock?",
    "How does the Bakery algorithm decide which process enters the critical section?",
    "How does the time quantum affect Round Robin scheduling?",
    "What is a Process Control Block?",
    "How do first-fit, best-fit and worst-fit allocation differ?",
    "What is the difference between a monolithic kernel and a microkernel?",
]

# --- paths ------------------------------------------------------------------
DATA_DIR = Path(os.getenv("BOOTUP_DATA_DIR", ROOT / "data" / "raw"))
INDEX_DIR = Path(os.getenv("BOOTUP_INDEX_DIR", ROOT / "index"))
EVAL_FILE = Path(os.getenv("BOOTUP_EVAL_FILE", ROOT / "eval" / "questions.json"))
RESULTS_DIR = Path(os.getenv("BOOTUP_RESULTS_DIR", ROOT / "eval" / "results"))

# Sub-folders of DATA_DIR that mean something.
SOURCE_TYPES = ("course", "open", "qa_bank")
