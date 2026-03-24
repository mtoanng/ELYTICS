import json
import pytest
from fastapi.testclient import TestClient

from backend.internal.auth import verify_oidc_token
from backend.main import app
import backend.routers.metadata as metadata_router


@pytest.fixture
def client():
    app.dependency_overrides[verify_oidc_token] = lambda: {
        "groups": ["IdM2BCD_holmes_pemely_user"],
        "email": "test@example.com",
    }
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_metadata_route_returns_distinct_data(client, monkeypatch):
    fake_data = [{"sample_id": "A", "type": "polcurve"}, {"sample_id": "A", "type": "polcurve"}]

    monkeypatch.setattr(metadata_router, "execute_sql_query", lambda q: fake_data)
    response = client.get("/api/sherlock/metadata/polcurve")
    assert response.status_code == 200
    assert response.json()["data"] == fake_data


def test_metadata_route_no_limit_offset_params(client, monkeypatch):
    monkeypatch.setattr(metadata_router, "execute_sql_query", lambda q: [])
    response = client.get("/api/sherlock/metadata/polcurve", params={"limit": 10, "offset": 5})
    assert response.status_code == 200


def test_metadata_cache_hit(client, monkeypatch):
    cached_data = [{"sample_id": "B"}]

    class FakeRedis:
        def get(self, key):
            return json.dumps(cached_data)
        def set(self, *a, **kw): pass
        def sadd(self, *a, **kw): pass

    monkeypatch.setattr(metadata_router, "get_redis_client", lambda: FakeRedis())
    response = client.get("/api/sherlock/metadata/polcurve")
    assert response.status_code == 200
    assert response.json()["data"] == cached_data
