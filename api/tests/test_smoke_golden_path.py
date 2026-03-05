import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _set_env_for_smoke():
    # Force CI/local smoke to avoid Azure dependencies
    os.environ["RETRIEVAL_BACKEND"] = "faiss"
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["EMBEDDINGS_PROVIDER"] = "mock"
    yield


@pytest.fixture(scope="session", autouse=True)
def _build_fixture_index_once():
    """
    Build FAISS index from fixtures for smoke tests.
    Uses EMBEDDINGS_PROVIDER=mock so no Azure OpenAI keys are needed.
    """
    api_dir = Path(__file__).resolve().parents[1]
    fixtures_dir = api_dir / "fixtures" / "raw"
    out_dir = api_dir / "data" / "index"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "ingest.build_faiss_index",
        "--input_dir",
        str(fixtures_dir),
        "--out_dir",
        str(out_dir),
    ]
    subprocess.check_call(cmd, cwd=str(api_dir))


@pytest.fixture()
def client():
    # Import after env is set
    from app.main import app

    return TestClient(app)


def test_golden_path_health_kb_chat_and_refusal(client):
    # health
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["retrieval_backend"] == "faiss"

    # kb (should work in faiss mode and return some docs)
    r = client.get("/kb")
    assert r.status_code == 200
    kb = r.json()
    assert isinstance(kb, list)
    assert len(kb) > 0

    # chat grounded answer path
    r = client.post("/chat", json={"message": "How do we triage a P1 incident?"})
    assert r.status_code == 200
    data = r.json()
    assert data["retrieval_backend"] == "faiss"
    assert isinstance(data["answer"], str)
    assert data["answer"].strip().startswith("- ")
    # citations should exist when answering grounded questions
    assert isinstance(data["citations"], list)
    assert len(data["citations"]) > 0

    # refusal path: SLA question should refuse and clear citations
    r = client.post("/chat", json={"message": "What is our SLA for P1 response time?"})
    assert r.status_code == 200
    data = r.json()
    assert "don't have enough information" in data["answer"].lower()
    assert data["citations"] == []