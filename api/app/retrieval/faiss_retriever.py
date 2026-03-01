import json
import os
from pathlib import Path

import faiss
import numpy as np
from dotenv import load_dotenv
from openai import AzureOpenAI

from .base import Retriever, RetrievedChunk

# Load .env for local runs
load_dotenv()


class FaissRetriever(Retriever):
    def __init__(self, index_dir: str = "data/index"):
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
        self.chunks = self._load_chunks(self.chunks_path)

        # Azure OpenAI client for query embedding
        self.client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        )
        self.embedding_model = os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"]

    def _load_chunks(self, path: Path) -> list[dict]:
        chunks = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                chunks.append(json.loads(line))
        return chunks

    def _embed_query(self, text: str) -> np.ndarray:
        resp = self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        vec = np.array(resp.data[0].embedding, dtype="float32")
        return vec

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        q = query.strip()
        if not q:
            return []

        qvec = self._embed_query(q).reshape(1, -1)

        # Search FAISS
        distances, indices = self.index.search(qvec, top_k)

        results: list[RetrievedChunk] = []
        for rank, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            meta = self.chunks[idx]
            # Convert distance to a "score" (simple heuristic: lower distance -> higher score)
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