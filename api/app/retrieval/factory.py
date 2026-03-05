from app.core.config import settings
from app.core.cache import cached, clear_cache

def get_retriever():
    backend = settings.retrieval_backend

    def _build():
        if backend == "azure_search":
            from .azure_search_retriever import AzureSearchRetriever
            return AzureSearchRetriever()
        from .faiss_retriever import FaissRetriever
        return FaissRetriever()

    # Cache retriever instance for this process for 10 minutes
    return cached(f"retriever:{backend}", ttl_seconds=600, fn=_build)


def reset_retriever_cache():
    clear_cache("retriever:")