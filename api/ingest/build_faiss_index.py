# api/ingest/build_faiss_index.py
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import faiss
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    from ingest.document_extractor import (
        IMAGE_EXTENSIONS,
        PDF_EXTENSIONS,
        TEXT_EXTENSIONS,
        extract_text_from_path,
        should_use_azure_fallback,
    )
except ModuleNotFoundError:
    from document_extractor import (  # type: ignore
        IMAGE_EXTENSIONS,
        PDF_EXTENSIONS,
        TEXT_EXTENSIONS,
        extract_text_from_path,
        should_use_azure_fallback,
    )

load_dotenv()

DEFAULT_DIM = int(os.environ.get("MOCK_EMBED_DIM", "384"))
DEFAULT_FAISS_NLIST = int(os.environ.get("FAISS_IVF_NLIST", "64"))


def chunk_text(text: str, chunk_size: int = 300, chunk_overlap: int = 50) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)

def mock_embed(text: str, dim: int = DEFAULT_DIM) -> list[float]:
    # Deterministic per-text embedding: seed from sha256(text)
    h = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(h[:8], "little", signed=False)
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(dim,)).astype("float32")
    # Normalize so cosine-ish behavior is stable
    v /= (np.linalg.norm(v) + 1e-8)
    return v.tolist()

def aoai_client():
    from openai import AzureOpenAI
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", default="data/raw")
    parser.add_argument("--out_dir", default="data/index")
    parser.add_argument("--chunk_size", type=int, default=300)
    parser.add_argument("--chunk_overlap", type=int, default=int(os.environ.get("CHUNK_OVERLAP", "50")))
    parser.add_argument("--provider", default=os.environ.get("EMBEDDINGS_PROVIDER", "aoai"))
    parser.add_argument(
        "--tenant-id",
        default=os.environ.get("DEFAULT_TENANT_ID", "default"),
        help="Tenant ID stamped into chunk metadata for retrieval isolation.",
    )
    parser.add_argument(
        "--ivf-nlist",
        type=int,
        default=DEFAULT_FAISS_NLIST,
        help="Number of IVF clusters (nlist) for IndexIVFFlat.",
    )
    parser.add_argument(
        "--ocr-provider",
        default=os.environ.get("OCR_PROVIDER", "auto"),
        help="OCR mode: auto, local, azure, or none.",
    )
    parser.add_argument(
        "--ocr-language",
        default=os.environ.get("OCR_LANGUAGE", "eng"),
        help="Language code for local Tesseract OCR.",
    )
    args = parser.parse_args()

    if args.chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0")
    if args.chunk_overlap >= args.chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    data_dir = Path(args.input_dir)
    index_dir = Path(args.out_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    supported_extensions = TEXT_EXTENSIONS | PDF_EXTENSIONS | IMAGE_EXTENSIONS
    files = [file for file in data_dir.iterdir() if file.is_file() and file.suffix.lower() in supported_extensions]
    if not files:
        raise FileNotFoundError(
            f"No input docs found in {data_dir} "
            "(expected txt, md, pdf, png, jpg, jpeg, tif, tiff, or bmp)"
        )

    chunks: list[dict] = []
    azure_fallback_enabled = should_use_azure_fallback()
    for file in files:
        text = extract_text_from_path(
            file,
            ocr_provider=args.ocr_provider,
            ocr_language=args.ocr_language,
            azure_fallback=azure_fallback_enabled,
        )
        if not text.strip():
            print(f"Skipping {file.name}: no extractable text found.")
            continue
        pieces = chunk_text(
            text,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
        for idx, piece in enumerate(pieces):
            chunks.append(
                {
                    "doc_id": file.stem,
                    "chunk_id": f"{file.stem}-{idx}",
                    "text": piece,
                    "tenant_id": args.tenant_id,
                }
            )

    if not chunks:
        raise ValueError("No chunks generated from input documents after extraction/OCR.")

    print(f"Total chunks: {len(chunks)}")

    embeddings: list[list[float]] = []
    if args.provider == "mock":
        embeddings = [mock_embed(c["text"]) for c in chunks]
    else:
        client = aoai_client()
        model = os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"]
        for c in chunks:
            resp = client.embeddings.create(model=model, input=c["text"])
            embeddings.append(resp.data[0].embedding)

    emb = np.array(embeddings, dtype="float32")
    dim = emb.shape[1]

    if len(chunks) < 2:
        # IVF requires training; for tiny corpora fall back to exact flat index.
        index = faiss.IndexFlatL2(dim)
        index.add(emb)
        print("Using IndexFlatL2 (fallback for very small dataset).")
    else:
        quantizer = faiss.IndexFlatL2(dim)
        nlist = max(1, min(args.ivf_nlist, len(chunks)))
        index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_L2)
        index.train(emb)
        index.add(emb)
        print(f"Using IndexIVFFlat (nlist={nlist}).")

    faiss.write_index(index, str(index_dir / "faiss.index"))
    with open(index_dir / "chunks.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")

    print("FAISS index built successfully.")

if __name__ == "__main__":
    main()