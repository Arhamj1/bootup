"""Assemble the deployment folders from an explicit allow-list.

    python tools/build_space.py [space|render]
        .space_build/app    code + built frontend (+ deploy files for the chosen target)
        .space_build/index  the search index, for the private Hugging Face dataset

Targets: "render" (default; light ONNX + numpy runtime on Render's free tier) or "space"
(Docker image for a Hugging Face Space).

Nothing else is copied: no slides, past papers, textbook, secrets.toml or virtualenv.
The script refuses to finish if a disallowed file or an API key ends up in either folder.
Build the frontend first (cd frontend && npm run build).
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".space_build"

TARGET_FILES = {
    "space": ["Dockerfile", "README.md", "requirements.txt"],
    "render": ["render.yaml", "README.md", "requirements.txt", "prefetch.py"],
}
REPO_GITIGNORE = "__pycache__/\n*.pyc\n.hf-cache/\nindex/\n.env\n"
APP_PY_DIRS = ["bootup", "server"]                  # only *.py from these
INDEX_FILES = ["meta.json", "stats.json", "chunks.jsonl", "vectors.npy"]
INDEX_DIRS = ["chroma"]

BANNED_SUFFIXES = {".pdf", ".pptx", ".ppt", ".docx", ".doc", ".toml", ".env", ".key"}
KEY_PATTERN = re.compile(rb"gsk_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{30,}")


def copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def check(folder: Path) -> list[str]:
    problems = []
    for f in folder.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() in BANNED_SUFFIXES:
            problems.append(f"disallowed file type: {f.relative_to(OUT)}")
        if KEY_PATTERN.search(f.read_bytes()):
            problems.append(f"looks like an API key inside: {f.relative_to(OUT)}")
    return problems


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "render"
    if target not in TARGET_FILES:
        print(f"Unknown target {target!r}; use one of {sorted(TARGET_FILES)}")
        return 1
    dist = ROOT / "frontend" / "dist"
    if not (dist / "index.html").exists():
        print("frontend/dist is missing. Run: cd frontend && npm run build")
        return 1
    if not (ROOT / "index" / "meta.json").exists():
        print("index/ is missing. Run: python -m bootup.build")
        return 1
    if OUT.exists():
        shutil.rmtree(OUT)
    app, index = OUT / "app", OUT / "index"

    app.mkdir(parents=True)
    for name in TARGET_FILES[target]:
        shutil.copy2(ROOT / "deploy" / target / name, app / name)
    (app / ".gitignore").write_text(REPO_GITIGNORE)
    for d in APP_PY_DIRS:
        for py in (ROOT / d).glob("*.py"):
            (app / d).mkdir(parents=True, exist_ok=True)
            shutil.copy2(py, app / d / py.name)
    copy_tree(dist, app / "frontend" / "dist")

    index.mkdir(parents=True)
    for name in INDEX_FILES:
        shutil.copy2(ROOT / "index" / name, index / name)
    for d in INDEX_DIRS:
        copy_tree(ROOT / "index" / d, index / d)

    problems = check(app) + check(index)
    if problems:
        shutil.rmtree(OUT)
        print("Refusing to continue:\n  " + "\n  ".join(problems))
        return 1

    for folder in (app, index):
        files = [f for f in folder.rglob("*") if f.is_file()]
        size = sum(f.stat().st_size for f in files) / 1e6
        print(f"{folder.relative_to(ROOT)}: {len(files)} files, {size:.1f} MB")
    print("App files:", ", ".join(sorted({str(p.relative_to(app)).split('\\')[0].split('/')[0]
                                          for p in app.iterdir()})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
