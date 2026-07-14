"""API tests using FastAPI's TestClient. The classifier is mocked."""

from fastapi.testclient import TestClient

import app.main as main


def test_health():
    client = TestClient(main.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_classify_endpoint(monkeypatch):
    monkeypatch.setattr(
        main, "classify_ticket", lambda text: {"category": "Delivery", "confidence": 0.88}
    )
    client = TestClient(main.app)
    response = client.post("/classify", json={"text": "My order hasn't arrived."})
    assert response.status_code == 200
    assert response.json() == {"category": "Delivery", "confidence": 0.88}


def test_classify_endpoint_rejects_empty_body():
    client = TestClient(main.app)
    response = client.post("/classify", json={"text": ""})
    assert response.status_code == 422


def test_classify_endpoint_propagates_unexpected_error(monkeypatch):
    def boom(text):
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "classify_ticket", boom)
    client = TestClient(main.app)
    response = client.post("/classify", json={"text": "hello"})
    assert response.status_code == 500
