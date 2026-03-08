from __future__ import annotations
import time
import hashlib
import json
import os
from pathlib import Path

import faiss
import numpy as np
from dotenv import load_dotenv

from .base import Retriever, RetrievedChunk

# Load .env for local runs (CI usually won't have one, that's fine)
load_dotenv()


def _mock_embed(text: str, dim: int) -> np.ndarray:
    """
    Deterministic embedding for CI / offline eval.
    Produces a normalized vector of length `dim` based on sha256(text).
    """
    h = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(h[:8], "little", signed=False)
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(dim,)).astype("float32")
    v /= (np.linalg.norm(v) + 1e-8)
    return v


class FaissRetriever(Retriever):
    def __init__(self, index_dir: str = "data/index"):
        self.last_embed_ms = 0
        self.last_search_ms = 0
        self.index_dir = Path(index_dir)
        self.index_path = self.index_dir / "faiss.index"
        self.chunks_path = self.index_dir / "chunks.jsonl"

        if not self.index_path.exists() or not self.chunks_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found. Expected {self.index_path} and {self.chunks_path}. "
                "Run: python ingest\\build_faiss_index.py"
            )

        # Load index + chunks metadata
        self.index = faiss.read_index(str(self.index_path))
        self.dim = int(getattr(self.index, "d", 0))  # embedding dimension from index
        self.chunks = self._load_chunks(self.chunks_path)

        # Embeddings provider:
        # - "aoai" (default) uses Azure OpenAI query embeddings
        # - "mock" uses deterministic local embeddings (CI-friendly, no secrets)
        self.provider = os.environ.get("EMBEDDINGS_PROVIDER", "mock").lower().strip()

        self.client = None
        self.embedding_model = None

        if self.provider == "aoai":
            # Import lazily so CI can run without AOAI env vars when provider=mock
            from openai import AzureOpenAI

            self.client = AzureOpenAI(
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_key=os.environ["AZURE_OPENAI_API_KEY"],
                api_version=os.environ["AZURE_OPENAI_API_VERSION"],
            )
            self.embedding_model = os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"]

    def _load_chunks(self, path: Path) -> list[dict]:
        chunks: list[dict] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                chunks.append(json.loads(line))
        return chunks

    def _embed_query(self, text: str) -> np.ndarray:
        t0 = time.perf_counter()

        # --- MOCK path (CI / offline)
        if self.provider == "mock":
            if self.dim <= 0:
                raise ValueError("FAISS index has invalid dimension (d <= 0).")

            vec = _mock_embed(text, self.dim)
            self.last_embed_ms = int((time.perf_counter() - t0) * 1000)
            return vec

        # --- AOAI path
        if self.client is None or self.embedding_model is None:
            raise RuntimeError(
                "AOAI embeddings selected but client/model not configured. "
                "Set EMBEDDINGS_PROVIDER=mock for CI or provide AZURE_OPENAI_* env vars."
            )

        resp = self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )

        self.last_embed_ms = int((time.perf_counter() - t0) * 1000)

        return np.array(resp.data[0].embedding, dtype="float32")

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        q = query.strip()
        if not q:
            return []

        import time

        t0 = time.perf_counter()
        qvec = self._embed_query(q).reshape(1, -1)
        self.last_embed_ms = int((time.perf_counter() - t0) * 1000)

        t1 = time.perf_counter()
        distances, indices = self.index.search(qvec, top_k)
        self.last_search_ms = int((time.perf_counter() - t1) * 1000)

        results: list[RetrievedChunk] = []
        for rank, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            meta = self.chunks[idx]
            dist = float(distances[0][rank])
            score = 1.0 / (1.0 + dist)

            results.append(
                RetrievedChunk(
                    doc_id=meta.get("doc_id", "unknown"),
                    chunk_id=meta.get("chunk_id", f"chunk-{idx}"),
                    title=meta.get("title"),
                    source_uri=meta.get("source_uri"),
                    score=score,
                    text=meta.get("text", ""),
                )
            )

        return results