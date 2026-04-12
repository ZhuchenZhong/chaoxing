from fastapi.testclient import TestClient


def test_create_app_exposes_health_endpoint():
    from chaoxing.main import create_app

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["version"] == "4.0.0-alpha.1"


def test_create_app_mounts_api_v1_root():
    from chaoxing.main import create_app

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Chaoxing Web API"
    assert payload["version"] == "4.0.0-alpha.1"
