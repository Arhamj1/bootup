"""Assemble the public source repository from an explicit allow-list.

    python tools/build_repo.py   ->  .space_build/repo

Copies the code, tests, docs and deployment files. Never copies course material (slides, notes,
textbook, past papers or questions transcribed from them), the index, virtualenvs or secrets, and
refuses to finish if a disallowed file type or an API key ends up in the folder.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".space_build" / "repo"

FILES = ["app.py", "pytest.ini", "requirements.txt", "README.md", "DEMO.md", "run_app.bat",
         "run_demo.bat", "run_demo.sh", ".streamlit/config.toml", "data/raw/README.md",
         "eval/questions.template.json",
         "frontend/index.html", "frontend/package.json", "frontend/package-lock.json",
         "frontend/tsconfig.json", "frontend/vite.config.ts"]
PY_DIRS = ["bootup", "server", "tests", "tools"]            # *.py only
TREES = ["frontend/src", "frontend/dist", "deploy"]          # whole folders
ROOT_FROM = {"render.yaml": "deploy/render/render.yaml"}     # Render reads its Blueprint from the root
GITIGNORE = """__pycache__/
*.pyc
.venv/
.pytest_cache/
frontend/node_modules/
index/
eval/results/
data/raw/*
!data/raw/README.md
data/past_papers/
data/excluded/
.streamlit/secrets.toml
.hf-cache/
.env
"""

BANNED_SUFFIXES = {".pdf", ".pptx", ".ppt", ".docx", ".doc", ".npy", ".jsonl", ".sqlite3", ".env", ".key"}
KEY_PATTERN = re.compile(rb"gsk_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{30,}")


def main() -> int:
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        print("Build the frontend first: cd frontend && npm run build")
        return 1
    git = OUT / ".git"
    keep_git = OUT.parent / "_repo_git"
    if git.exists():                      # keep history across rebuilds
        shutil.move(str(git), str(keep_git))
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    if keep_git.exists():
        shutil.move(str(keep_git), str(git))

    for rel in FILES:
        src = ROOT / rel
        if src.exists():
            (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, OUT / rel)
    for d in PY_DIRS:
        for py in (ROOT / d).glob("*.py"):
            (OUT / d).mkdir(parents=True, exist_ok=True)
            shutil.copy2(py, OUT / d / py.name)
    for d in TREES:
        shutil.copytree(ROOT / d, OUT / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for dst, src in ROOT_FROM.items():
        shutil.copy2(ROOT / src, OUT / dst)
    (OUT / ".gitignore").write_text(GITIGNORE)

    problems = []
    for f in OUT.rglob("*"):
        if not f.is_file() or ".git" in f.relative_to(OUT).parts:
            continue
        if f.suffix.lower() in BANNED_SUFFIXES:
            problems.append(f"disallowed file type: {f.relative_to(OUT)}")
        if KEY_PATTERN.search(f.read_bytes()):
            problems.append(f"looks like an API key inside: {f.relative_to(OUT)}")
    if problems:
        print("Refusing to continue:\n  " + "\n  ".join(problems))
        return 1
    files = [f for f in OUT.rglob("*") if f.is_file() and ".git" not in f.relative_to(OUT).parts]
    print(f"{OUT.relative_to(ROOT)}: {len(files)} files, {sum(f.stat().st_size for f in files) / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
