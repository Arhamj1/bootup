"""Run during Render's build: download the ONNX model and the private index once,
so a cold start does not have to. Needs HF_TOKEN (read) and BOOTUP_INDEX_REPO."""
import os

from huggingface_hub import hf_hub_download, snapshot_download

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
for name in ("tokenizer.json", "config.json", "onnx/model.onnx"):
    hf_hub_download(MODEL, name)
print("model files cached")

repo = os.environ.get("BOOTUP_INDEX_REPO")
if repo:
    snapshot_download(repo_id=repo, repo_type="dataset", local_dir=os.environ.get("BOOTUP_INDEX_DIR", "index"),
                      token=os.environ.get("HF_TOKEN"), allow_patterns=["*.json", "*.jsonl", "*.npy"])
    print("index downloaded from", repo)
else:
    print("BOOTUP_INDEX_REPO not set: the index will be fetched at start-up")
