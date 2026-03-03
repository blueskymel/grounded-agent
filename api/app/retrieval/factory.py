from app.core.config import settings
from .base import Retriever
# api/app/retrieval/factory.py
import os

def get_retriever():
    backend = os.getenv("RETRIEVAL_BACKEND", "faiss").lower()

    if backend == "azure_search":
        from .azure_search_retriever import AzureSearchRetriever
        return AzureSearchRetriever()

    # default: faiss
    from .faiss_retriever import FaissRetriever
    return FaissRetriever()