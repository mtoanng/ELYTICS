from fastapi.testclient import TestClient

from backend.main import app


def test_legacy_metadata_routes_are_not_mounted():
    with TestClient(app) as client:
        response = client.get("/api/sherlock/metadata/polcurve")

    assert response.status_code == 404
