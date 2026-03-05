import json
import os
from collections import Counter
from pathlib import Path
from app.core.cache import cached

def faiss_doc_stats():
    return cached("kb:faiss_doc_stats", ttl_seconds=30, fn=_faiss_doc_stats_uncached)

def azure_search_doc_stats():
    return cached("kb:azure_search_doc_stats", ttl_seconds=30, fn=_azure_search_doc_stats_uncached)


# -------------------------
# FAISS mode
# -------------------------
def _faiss_doc_stats_uncached(index_dir: str = "data/index") -> list[dict]:
    chunks_path = Path(index_dir) / "chunks.jsonl"
    if not chunks_path.exists():
        return []

    counter = Counter()

    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            counter[obj.get("doc_id", "unknown")] += 1

    return [
        {"doc_id": k, "chunks": v}
        for k, v in sorted(counter.items())
    ]


# -------------------------
# Azure AI Search mode
# -------------------------
def _azure_search_doc_stats_uncached() -> list[dict]:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    key = os.environ.get("AZURE_SEARCH_API_KEY")
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME")

    if not endpoint or not key or not index_name:
        return []

    client = SearchClient(
        endpoint,
        index_name,
        AzureKeyCredential(key),
    )

    # For demo-scale KB, this is fine
    results = client.search(
        search_text="*",
        select=["doc_id"],
        top=1000,
    )

    counter = Counter()

    for r in results:
        counter[r.get("doc_id", "unknown")] += 1

    return [
        {"doc_id": k, "chunks": v}
        for k, v in sorted(counter.items())
    ]