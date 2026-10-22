---
title: BootUp
emoji: 📘
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# BootUp

An Operating Systems study assistant that answers only from the loaded course material and shows
which slide or page each answer came from. Hybrid retrieval (embeddings + BM25, fused with
Reciprocal Rank Fusion), answers streamed from a Groq-hosted model.

The site asks for an access code. The search index is loaded from a private dataset at start-up
and is not part of this repository.

Space secrets: `GROQ_API_KEY`, `BOOTUP_ACCESS_CODE`, `HF_TOKEN` (read access to the index dataset).
Space variable: `BOOTUP_INDEX_REPO` (for example `your-name/bootup-index`).
