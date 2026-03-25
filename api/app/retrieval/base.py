from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    doc_id: str
    chunk_id: str
    title: str | None
    source_uri: str | None
    score: float | None
    text: str


class Retriever(ABC):
    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        tenant_id: str | None = None,
    ) -> list[RetrievedChunk]:
        raise NotImplementedError