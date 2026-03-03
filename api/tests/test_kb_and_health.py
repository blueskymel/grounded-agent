def test_health_has_backend(client, monkeypatch):
    from app.core import config
    monkeypatch.setattr(config.settings, "retrieval_backend", "faiss", raising=False)

    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["retrieval_backend"] == "faiss"


def test_kb_uses_faiss_in_faiss_mode(client, monkeypatch):
    from app.core import config
    import app.main as main_mod

    monkeypatch.setattr(config.settings, "retrieval_backend", "faiss", raising=False)

    # Patch the imported function in app.main (because main.py imported it directly)
    monkeypatch.setattr(main_mod, "faiss_doc_stats", lambda: [{"doc_id": "d1", "chunks": 3}])
    monkeypatch.setattr(main_mod, "azure_search_doc_stats", lambda: [{"doc_id": "AZ", "chunks": 999}])

    r = client.get("/kb")
    assert r.status_code == 200
    assert r.json() == [{"doc_id": "d1", "chunks": 3}]