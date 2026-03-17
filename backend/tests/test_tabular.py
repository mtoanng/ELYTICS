import pytest
from fastapi.testclient import TestClient

from backend.internal.auth import verify_oidc_token
from backend.main import app
import backend.routers.tabular as tabular_router


@pytest.fixture
def client():
    app.dependency_overrides[verify_oidc_token] = lambda: {
        "groups": ["IdM2BCD_holmes_pemely_user"],
        "email": "test@example.com",
    }
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_tabular_route_with_limit_offset(client, monkeypatch):
    def fake_get_query_result(**kwargs):
        assert kwargs["limit"] == 10
        assert kwargs["offset"] == 5
        return [{"row_id": 1}]

    monkeypatch.setattr(tabular_router, "get_query_result", fake_get_query_result)
    response = client.get("/api/sherlock/tabular/order", params={"limit": 10, "offset": 5})
    assert response.status_code == 200
    assert response.json() == {"data": [{"row_id": 1}]}


def test_tabular_route_missing_required_filter(client):
    response = client.get("/api/sherlock/tabular/track_record", params={"limit": 10})
    assert response.status_code == 400
    assert "order_id" in response.json()["detail"]


def test_tabular_route_invalid_sort_dir(client, monkeypatch):
    monkeypatch.setattr(tabular_router, "get_query_result", lambda **_: [])
    response = client.get("/api/sherlock/tabular/order", params={"sort_dir": "sideways"})
    assert response.status_code == 400
