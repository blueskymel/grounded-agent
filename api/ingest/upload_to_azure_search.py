import os
import json
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

load_dotenv()

INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "groundedagent-chunks")
DEFAULT_TENANT_ID = os.environ.get("DEFAULT_TENANT_ID", "default")


def main():
    print("Starting upload to Azure AI Search...")

    # --- Azure AI Search ---
    search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    search_key = os.environ["AZURE_SEARCH_API_KEY"]

    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(search_key),
    )

    # --- Azure OpenAI (Embeddings) ---
    aoai = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )

    emb_deployment = os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"]

    chunks_path = "data/index/chunks.jsonl"

    if not os.path.exists(chunks_path):
        raise FileNotFoundError("chunks.jsonl not found. Run FAISS ingestion first.")

    docs = []
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)

            print(f"Embedding chunk {chunk['chunk_id']}...")

            emb = aoai.embeddings.create(
                model=emb_deployment,
                input=chunk["text"],
            )

            vector = emb.data[0].embedding

            doc = {
                "id": chunk["chunk_id"],  # key field
                "doc_id": chunk["doc_id"],
                "chunk_id": chunk["chunk_id"],
                "tenant_id": chunk.get("tenant_id", DEFAULT_TENANT_ID),
                "title": chunk.get("title"),
                "source_uri": chunk.get("source_uri"),
                "content": chunk["text"],
                "contentVector": vector,
            }

            docs.append(doc)

    print(f"Uploading {len(docs)} documents to Azure Search...")

    result = search_client.upload_documents(documents=docs)

    failed = [r for r in result if not r.succeeded]

    print(f"Upload complete. Total: {len(docs)}, Failed: {len(failed)}")

    if failed:
        print("First failure:", failed[0])


if __name__ == "__main__":
    main()