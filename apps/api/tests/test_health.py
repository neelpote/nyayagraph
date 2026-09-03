from fastapi.testclient import TestClient

from app.main import app


def test_root_and_versioned_health_endpoints_are_available():
    client = TestClient(app)
    root = client.get("/health")
    versioned = client.get("/api/v1/health")

    assert root.status_code == versioned.status_code == 200
    assert root.json()["api"] == versioned.json()["api"] == "ok"
