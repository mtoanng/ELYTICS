import pytest
from fastapi.testclient import TestClient

from backend.services.auth import verify_oidc_token
from backend.main import app
import backend.routers.timeseries as timeseries_router


@pytest.fixture
def client():
    app.dependency_overrides[verify_oidc_token] = lambda: {
        "groups": ["IdM2BCD_holmes_pemely_user"],
        "email": "test@example.com",
    }
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_timeseries_endpoint_returns_bucketed_payload(client, monkeypatch):
    def fake_get_timeseries_result(**kwargs):
        assert kwargs["time_column"] == "time"
        assert kwargs["value_columns"] == ["uCell"]
        assert kwargs["filters"]["order_id"] == ["ord-1"]
        return {
            "data": [{"bucket_start": "2025-01-01T00:00:00Z", "uCell_min": 1, "uCell_max": 5, "uCell_avg": 3}],
            "meta": {"bucket_seconds": 60, "requested_points": 1200, "returned_points": 1},
        }

    monkeypatch.setattr(timeseries_router, "get_timeseries_result", fake_get_timeseries_result)
    response = client.get(
        "/api/sherlock/timeseries/timeseries_exp",
        params={
            "start": "2025-01-01T00:00:00Z",
            "end": "2025-01-01T01:00:00Z",
            "columns": ["uCell"],
            "time_column": "time",
            "order_id": "ord-1",
        },
    )
    assert response.status_code == 200
    assert response.json()["meta"]["bucket_seconds"] == 60


def test_timeseries_endpoint_requires_order_id(client):
    response = client.get(
        "/api/sherlock/timeseries/timeseries_exp",
        params={
            "start": "2025-01-01T00:00:00Z",
            "end": "2025-01-01T01:00:00Z",
            "columns": ["uCell"],
            "time_column": "time",
        },
    )
    assert response.status_code == 400
    assert "order_id" in response.json()["detail"]
