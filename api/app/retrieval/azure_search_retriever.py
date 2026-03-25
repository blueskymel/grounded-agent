import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from .base import Retriever, RetrievedChunk

load_dotenv()


class AzureSearchRetriever(Retriever):
    def __init__(self):
        endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
        index_name = os.environ["AZURE_SEARCH_INDEX_NAME"]
        api_key = os.environ["AZURE_SEARCH_API_KEY"]

        self.search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(api_key),
        )

        # For vector queries we need query embeddings
        self.aoai = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        )
        self.embedding_model = os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"]

    def _embed_query(self, text: str) -> list[float]:
        resp = self.aoai.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        return resp.data[0].embedding

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        tenant_id: str | None = None,
    ) -> list[RetrievedChunk]:
        q = query.strip()
        if not q:
            return []

        vector = self._embed_query(q)

        search_filter = None
        if tenant_id:
            safe_tenant = tenant_id.replace("'", "''")
            search_filter = f"tenant_id eq '{safe_tenant}'"

        # Hybrid search: keyword + vector. (Works well for RAG)
        results = self.search_client.search(
            search_text=q,
            top=top_k,
            vector_queries=[{
                "kind": "vector",
                "vector": vector,
                "fields": "contentVector",
                "k": top_k,
            }],
            filter=search_filter,
            select=["doc_id", "chunk_id", "title", "source_uri", "content"],
        )

        chunks: list[RetrievedChunk] = []
        for r in results:
            chunks.append(
                RetrievedChunk(
                    doc_id=r.get("doc_id", "unknown"),
                    chunk_id=r.get("chunk_id", ""),
                    title=r.get("title"),
                    source_uri=r.get("source_uri"),
                    score=r.get("@search.score"),
                    text=r.get("content", ""),
                )
            )

        return chunks