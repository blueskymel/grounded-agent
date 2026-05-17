"""
SemanticMemory: Simple vector store for semantic retrieval of prior decisions, facts, workflows.
Uses FAISS for vector search. Demo-friendly, enterprise-relevant.
"""
from typing import List, Dict, Any
import numpy as np
import faiss

class SemanticMemory:
    def __init__(self, embedding_fn, dim: int = 384):
        self.embedding_fn = embedding_fn
        self.dim = dim
        self.index = faiss.IndexFlatL2(dim)
        self.entries: List[Dict[str, Any]] = []
        self.embeddings = []

    def add_entry(self, text: str, meta: Dict[str, Any]):
        vec = self.embedding_fn(text)
        vec = np.array(vec).astype('float32').reshape(1, -1)
        self.index.add(vec)
        self.entries.append({"text": text, "meta": meta})
        self.embeddings.append(vec)

    def search(self, query: str, top_k: int = 3):
        if len(self.entries) == 0:
            return []
        qvec = self.embedding_fn(query)
        qvec = np.array(qvec).astype('float32').reshape(1, -1)
        D, I = self.index.search(qvec, top_k)
        results = []
        for idx, dist in zip(I[0], D[0]):
            if idx < len(self.entries):
                entry = self.entries[idx]
                entry = dict(entry)  # copy
                entry['score'] = float(dist)
                results.append(entry)
        return results

    def clear(self):
        self.index.reset()
        self.entries.clear()
        self.embeddings.clear()
