from app.core.config import settings
from .base import Retriever
from .faiss_retriever import FaissRetriever
from .azure_search_retriever import AzureSearchRetriever


def get_retriever() -> Retriever:
    backend = (settings.retrieval_backend or "faiss").lower().strip()
    if backend == "azure_search":
        return AzureSearchRetriever()
    return FaissRetriever()