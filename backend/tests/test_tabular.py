import pytest
from fastapi.testclient import TestClient

from backend.services.auth import verify_oidc_token
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


def test_tabular_route_ignores_limit_offset_params(client, monkeypatch):
    def fake_get_query_result(**kwargs):
        assert "limit" not in kwargs
        assert "offset" not in kwargs
        return [{"row_id": 1}]

    monkeypatch.setattr(tabular_router, "get_query_result", fake_get_query_result)
    response = client.get("/api/sherlock/tabular/order", params={"limit": 10, "offset": 5})
    assert response.status_code == 200
    assert response.json() == {"data": [{"row_id": 1}]}


def test_tabular_route_missing_required_filter(client):
    response = client.get("/api/sherlock/tabular/track_record")
    assert response.status_code == 400
    assert "order_id" in response.json()["detail"]


def test_tabular_route_invalid_sort_dir(client, monkeypatch):
    monkeypatch.setattr(tabular_router, "get_query_result", lambda **_: [])
    response = client.get("/api/sherlock/tabular/order", params={"sort_dir": "sideways"})
    assert response.status_code == 400


def test_soh_stack_requires_sample_name(client):
    response = client.get("/api/sherlock/tabular/soh_stack")
    assert response.status_code == 400
    assert "sample_name" in response.json()["detail"]


def test_soh_fleet_route_available(client, monkeypatch):
    monkeypatch.setattr(tabular_router, "get_query_result", lambda **_: [{"sample_name": "A"}])
    response = client.get("/api/sherlock/tabular/soh_fleet")
    assert response.status_code == 200
    assert response.json() == {"data": [{"sample_name": "A"}]}


def test_soh_stack_passes_sample_filter(client, monkeypatch):
    def fake_get_query_result(**kwargs):
        assert kwargs["filters"]["sample_name"] == ["sample_001"]
        return [{"sample_name": "sample_001"}]

    monkeypatch.setattr(tabular_router, "get_query_result", fake_get_query_result)
    response = client.get("/api/sherlock/tabular/soh_stack", params={"sample_name": "sample_001"})
    assert response.status_code == 200
    assert response.json() == {"data": [{"sample_name": "sample_001"}]}
