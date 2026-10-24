# BootUp

An Operating Systems study assistant that answers from the loaded course material and shows
which slide or page each answer came from. Hybrid retrieval (embeddings + BM25, fused with
Reciprocal Rank Fusion); answers streamed from a Groq-hosted model.

This repository holds code only. The search index is downloaded at build time from a private
Hugging Face dataset, and the site asks visitors for an access code.

Deployed on Render from `render.yaml`. Secrets (set in the Render dashboard, never committed):
`GROQ_API_KEY`, `BOOTUP_ACCESS_CODE`, `HF_TOKEN` (read access to the index dataset).
