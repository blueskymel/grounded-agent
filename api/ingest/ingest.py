import os
import subprocess
import sys
from dotenv import load_dotenv

load_dotenv()

def run(cmd: list[str]) -> None:
    print("\n>>", " ".join(cmd))
    subprocess.check_call(cmd)

def main():
    # Always rebuild local FAISS index + chunks.jsonl
    run([sys.executable, "ingest/build_faiss_index.py"])

    backend = os.environ.get("RETRIEVAL_BACKEND", "faiss").lower()

    # Optional: if enterprise mode, also sync to Azure AI Search
    if backend == "azure_search":
        run([sys.executable, "ingest/upload_to_azure_search.py"])
        print("\nDone: FAISS rebuilt + Azure Search synced.")
    else:
        print("\nDone: FAISS rebuilt (demo mode).")

if __name__ == "__main__":
    main()