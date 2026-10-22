# BootUp on a Hugging Face Space (Docker SDK). Built from the folder made by tools/build_space.py.
# The image holds code + the built frontend + the embedding model. The search index is NOT in the
# image: it is downloaded at start-up from a private dataset (BOOTUP_INDEX_REPO, using HF_TOKEN).
FROM python:3.12-slim

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface
WORKDIR /home/user/app

# CPU-only PyTorch first (the default PyPI wheel bundles CUDA and is several GB).
RUN pip install --no-cache-dir --user --index-url https://download.pytorch.org/whl/cpu torch
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Download the embedding model at build time so start-up does not depend on it.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY --chown=user bootup ./bootup
COPY --chown=user server ./server
COPY --chown=user frontend/dist ./frontend/dist

ENV BOOTUP_PUBLIC=1 \
    BOOTUP_INDEX_DIR=/home/user/app/index
EXPOSE 7860
CMD ["python", "-m", "server", "--host", "0.0.0.0", "--port", "7860"]
