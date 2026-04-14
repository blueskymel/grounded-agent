FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY api /app

ENV APP_ENV=dev
ENV RETRIEVAL_BACKEND=faiss
ENV EMBEDDINGS_PROVIDER=mock
ENV LLM_PROVIDER=mock

# Build FAISS index from committed raw docs at image build time (no Azure creds needed)
RUN EMBEDDINGS_PROVIDER=mock python ingest/build_faiss_index.py \
    --input_dir data/raw \
    --out_dir data/index \
    --provider mock

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]