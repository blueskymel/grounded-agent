import os
import json
import numpy as np
import faiss
from pathlib import Path
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

DATA_DIR = Path("data/raw")
INDEX_DIR = Path("data/index")
INDEX_DIR.mkdir(parents=True, exist_ok=True)

client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
)

EMBEDDING_MODEL = os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"]

def chunk_text(text, chunk_size=300):
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def main():
    chunks = []
    for file in DATA_DIR.glob("*.txt"):
        text = file.read_text(encoding="utf-8")
        pieces = chunk_text(text)
        for idx, piece in enumerate(pieces):
            chunks.append({
                "doc_id": file.stem,
                "chunk_id": f"{file.stem}-{idx}",
                "text": piece
            })

    print(f"Total chunks: {len(chunks)}")

    embeddings = []
    for chunk in chunks:
        resp = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=chunk["text"]
        )
        vector = resp.data[0].embedding
        embeddings.append(vector)

    embeddings_np = np.array(embeddings).astype("float32")
    dimension = embeddings_np.shape[1]

    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings_np)

    faiss.write_index(index, str(INDEX_DIR / "faiss.index"))

    with open(INDEX_DIR / "chunks.jsonl", "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")

    print("FAISS index built successfully.")

if __name__ == "__main__":
    main()