from fastapi.testclient import TestClient

from backend.main import app


def test_legacy_timeseries_routes_are_not_mounted():
    with TestClient(app) as client:
        response = client.get("/api/sherlock/timeseries/timeseries_exp")

    assert response.status_code == 404
