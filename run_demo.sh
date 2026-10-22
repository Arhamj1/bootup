#!/usr/bin/env bash
# BootUp demo launcher for macOS / Linux:  bash run_demo.sh
set -euo pipefail
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python || true)
[ -n "$PY" ] || { echo "Python 3.11 or 3.12 is required."; exit 1; }

[ -x .venv/bin/python ] || { echo "Creating a virtual environment..."; "$PY" -m venv .venv; }
# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f .venv/installed.flag ]; then
  echo "Installing packages. First time only - this can take several minutes..."
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  touch .venv/installed.flag
fi

if [ ! -f .streamlit/secrets.toml ] && [ -z "${GROQ_API_KEY:-}" ]; then
  read -r -p "Paste your Groq API key and press Enter (or just press Enter to skip): " KEY || true
  if [ -n "${KEY:-}" ]; then
    mkdir -p .streamlit
    printf 'GROQ_API_KEY = "%s"\n' "$KEY" > .streamlit/secrets.toml
    chmod 600 .streamlit/secrets.toml
    echo "Saved the key to .streamlit/secrets.toml (never shared or committed)."
  fi
fi

if [ ! -f index/meta.json ]; then
  echo "Building the index from data/raw. The first build downloads the embedding model..."
  python -m bootup.build
fi

echo "Starting BootUp. It opens in your browser; press Ctrl+C here to stop it."
python -m streamlit run app.py
