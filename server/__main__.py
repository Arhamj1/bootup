"""python -m server [--port 8000]   starts the BootUp API (and the built frontend, if present)."""
import argparse

import uvicorn

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8000)
args = parser.parse_args()
uvicorn.run("server.api:app", host=args.host, port=args.port)
