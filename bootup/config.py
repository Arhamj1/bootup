"""Settings. Paths and model names can also be set with environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Models
EMBED_MODEL = os.getenv("BOOTUP_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
LLM_MODEL = os.getenv("BOOTUP_LLM_MODEL", "openai/gpt-oss-20b")

# Chunking
# Sizes are approximate: tokens are converted to words with WORDS_PER_TOKEN.
# all-MiniLM-L6-v2 ignores input beyond 256 tokens, so stay well below that.
CHUNK_TOKENS = 200
WORDS_PER_TOKEN = 0.75
OVERLAP_FRACTION = 0.15
MIN_MERGE_WORDS = 40        # consecutive slides shorter than this get merged
DEDUPE_THRESHOLD = 0.95     # cosine similarity above which chunks count as duplicates

# Retrieval
TOP_K_EACH = 10             # chunks taken from each retriever before fusion
TOP_K_FINAL = 4             # chunks passed to the LLM after fusion
RRF_K = 60

# Generation
TEMPERATURE = 0.2
# For reasoning models (gpt-oss) this budget also covers the hidden reasoning, which can use
# several hundred tokens on calculation questions before any answer text is written.
MAX_ANSWER_TOKENS = 2048
REASONING_EFFORT = "low"                 # "low" | "medium" | "high"; only sent to reasoning models
REASONING_MODEL_PREFIXES = ("openai/gpt-oss",)
# Rewrite the question into textbook keywords before searching (one extra short model call).
QUERY_EXPANSION = os.getenv("BOOTUP_QUERY_EXPANSION", "1") != "0"
EXPAND_MAX_TOKENS = 600

# Example questions shown on the start page (taken from the course slides).
DEMO_QUESTIONS = [
    "What are the four necessary conditions for a deadlock?",
    "How does the Bakery algorithm decide which process enters the critical section?",
    "How does the time quantum affect Round Robin scheduling?",
    "What is a Process Control Block?",
    "How do first-fit, best-fit and worst-fit allocation differ?",
    "What is the difference between a monolithic kernel and a microkernel?",
]

# Paths
DATA_DIR = Path(os.getenv("BOOTUP_DATA_DIR", ROOT / "data" / "raw"))
INDEX_DIR = Path(os.getenv("BOOTUP_INDEX_DIR", ROOT / "index"))
EVAL_FILE = Path(os.getenv("BOOTUP_EVAL_FILE", ROOT / "eval" / "questions.json"))
RESULTS_DIR = Path(os.getenv("BOOTUP_RESULTS_DIR", ROOT / "eval" / "results"))

# Top-level folders under DATA_DIR that set a chunk's source type.
SOURCE_TYPES = ("course", "open", "qa_bank")
