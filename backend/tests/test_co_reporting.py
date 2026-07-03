from fastapi.testclient import TestClient
import pytest

from backend.main import app
from backend.services.auth import verify_oidc_token
import backend.routers.co_reporting as co_reporting_router


@pytest.fixture
def client():
    app.dependency_overrides[verify_oidc_token] = lambda: {
        "groups": ["IdM2BCD_holmes_pemely_development"],
        "email": "test@example.com",
    }
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_co_reporting_query_endpoint_returns_windowed_payload(client, monkeypatch):
    def fake_query_timeseries_window(**kwargs):
        assert kwargs["series"] == "PoC Stack VI"
        assert kwargs["uuid"] == "uuid-1"
        assert kwargs["group"] == "Conditioning"
        assert kwargs["channels"] == ["Stack Voltage", "Current density"]
        assert kwargs["visible_start_s"] == 0
        assert kwargs["visible_end_s"] == 7200
        assert kwargs["prefetch_margin_s"] == 900
        assert kwargs["resolution"] == "auto"
        assert kwargs["mode"] == "standard_report"
        assert kwargs["report_id"] == "eff-main"
        assert kwargs["include_band"] is True
        return {
            "data": [{"elapsed_time_s": 0, "channel_name": "Stack Voltage", "value_mean": 14.2}],
            "meta": {
                "served_resolution": "agg_1m",
                "returned_points": 1,
                "query_start_s": 0,
                "query_end_s": 8100,
            },
        }

    monkeypatch.setattr(co_reporting_router, "query_timeseries_window", fake_query_timeseries_window)
    response = client.post(
        "/api/sherlock/co-reporting/query",
        json={
            "series": "PoC Stack VI",
            "uuid": "uuid-1",
            "group": "Conditioning",
            "channels": ["Stack Voltage", "Current density"],
            "visible_start_s": 0,
            "visible_end_s": 7200,
            "prefetch_margin_s": 900,
            "resolution": "auto",
            "mode": "standard_report",
            "report_id": "eff-main",
            "include_band": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["served_resolution"] == "agg_1m"
    assert payload["meta"]["returned_points"] == 1


def test_co_reporting_query_requires_channels(client):
    response = client.post(
        "/api/sherlock/co-reporting/query",
        json={
            "series": "PoC Stack VI",
            "uuid": "uuid-1",
            "group": "Conditioning",
            "channels": [],
            "visible_start_s": 0,
            "visible_end_s": 7200,
        },
    )
    assert response.status_code == 422
