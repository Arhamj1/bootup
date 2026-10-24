"""Ingest everything under data/raw and build the indexes.

    python -m bootup.build
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from . import config
from .embed import get_embedder
from .index import build_index
from .ingest import ingest_all


def dataset_stats(chunks, files, skipped, dropped) -> dict:
    words = [len(c.text.split()) for c in chunks]
    by_type = Counter(c.source_type for c in chunks)
    by_topic = Counter(c.topic for c in chunks)
    files_by_type = Counter(f.split("/")[0] if f.split("/")[0] in config.SOURCE_TYPES else "course"
                            for f in files)
    return {
        "files_used": len(files),
        "files_by_source_type": dict(files_by_type),
        "files_skipped": [{"file": f, "reason": r} for f, r in skipped],
        "chunks_before_dedupe": len(chunks),
        "duplicates_dropped": len(dropped),
        "chunks_by_source_type": dict(by_type),
        "chunks_by_topic": dict(by_topic),
        "words_per_chunk": {
            "mean": round(statistics.mean(words), 1) if words else 0,
            "median": statistics.median(words) if words else 0,
            "max": max(words) if words else 0,
        },
    }


def run_build(data_dir: Path, index_dir: Path, embedder) -> dict:
    """Ingest data_dir, build both indexes in index_dir, save and return statistics."""
    chunks, files, skipped = ingest_all(data_dir)
    if not chunks:
        raise ValueError(f"No readable files under {data_dir}. Add your material there first.")
    meta = build_index(chunks, embedder, index_dir)
    stats = dataset_stats(chunks, files, skipped, meta["dropped"])
    stats.update(embedder=meta["embedder"], chunks_indexed=meta["n_chunks"],
                 built_at=meta["built_at"])
    (index_dir / "stats.json").write_text(json.dumps(stats, indent=2))
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=config.DATA_DIR)
    ap.add_argument("--index-dir", type=Path, default=config.INDEX_DIR)
    ap.add_argument("--embedder", default=config.EMBED_MODEL,
                    help="model name, or 'standin' for the offline test stand-in")
    args = ap.parse_args(argv)

    embedder = get_embedder(args.embedder)
    if embedder.is_standin:
        print("Note: stand-in embedder, for testing the code only.\n")
    try:
        stats = run_build(args.data_dir, args.index_dir, embedder)
    except ValueError as exc:
        print(exc)
        return 1
    print(f"Read {stats['files_used']} files -> {stats['chunks_before_dedupe']} chunks")
    for s in stats["files_skipped"]:
        print(f"  skipped {s['file']}: {s['reason']}")
    print(f"Indexed {stats['chunks_indexed']} chunks "
          f"({stats['duplicates_dropped']} near-duplicates dropped)")
    print(json.dumps({k: stats[k] for k in ("chunks_by_source_type", "chunks_by_topic",
                                            "words_per_chunk")}, indent=2))
    print(f"Full statistics saved to {args.index_dir / 'stats.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
