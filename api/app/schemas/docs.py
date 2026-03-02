from pydantic import BaseModel


class DocSummary(BaseModel):
    doc_id: str
    chunks: int