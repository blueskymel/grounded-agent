# api/app/retrieval/factory.py
from app.core.config import settings
from .base import Retriever

def get_retriever() -> Retriever:
    backend = (settings.retrieval_backend or "faiss").lower().strip()

    if backend == "azure_search":
        from .azure_search_retriever import AzureSearchRetriever
        return AzureSearchRetriever()

    from .faiss_retriever import FaissRetriever
    return FaissRetriever()