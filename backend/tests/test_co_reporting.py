from fastapi.testclient import TestClient
import pytest

from backend.main import app
from backend.services.auth import verify_oidc_token
import backend.routers.co_reporting as co_reporting_router
import backend.services.co_reporting as co_reporting_service


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
        assert kwargs["experiment_id"] == 42
        assert kwargs["uuid"] == "run-uuid-001"
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
        "/api/elytics/co-reporting/query",
        json={
            "series": "PoC Stack VI",
            "experiment_id": 42,
            "uuid": "run-uuid-001",
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
        "/api/elytics/co-reporting/query",
        json={
            "series": "PoC Stack VI",
            "experiment_id": 42,
            "channels": [],
            "visible_start_s": 0,
            "visible_end_s": 7200,
        },
    )
    assert response.status_code == 422


def test_co_reporting_channel_query_uses_full_gold_identity(monkeypatch):
    captured = {}

    def fake_cache_get_or_query(key_prefix, query, source_name, **key_parts):
        captured["key_prefix"] = key_prefix
        captured["query"] = query
        captured["source_name"] = source_name
        captured["key_parts"] = key_parts
        return []

    monkeypatch.setattr(co_reporting_service, "_cache_get_or_query", fake_cache_get_or_query)

    co_reporting_service.list_channels(
        series="PoC Stack VI",
        experiment_id=42,
        uuid="run-uuid-001",
        group="Conditioning",
    )

    query = captured["query"]
    assert captured["key_prefix"] == "co_reporting_channels"
    assert "FROM ps_xplatform_dev.co2elyd_dev.gold_channel_catalog_experiment" in query
    assert "series = 'PoC Stack VI'" in query
    assert "experiment_id = 42" in query
    assert "uuid = 'run-uuid-001'" in query
    assert "`group` = 'Conditioning'" in query
    assert "std_channel AS channel_name" in query


def test_co_reporting_window_query_can_use_uuid_group_identity(monkeypatch):
    captured = {}

    def fake_cache_get_or_query(key_prefix, query, source_name, **key_parts):
        captured["key_prefix"] = key_prefix
        captured["query"] = query
        captured["source_name"] = source_name
        captured["key_parts"] = key_parts
        return [{"elapsed_time_s": 60, "std_channel": "Stack Voltage", "value_mean": 14.2}]

    monkeypatch.setattr(co_reporting_service, "_cache_get_or_query", fake_cache_get_or_query)

    payload = co_reporting_service.query_timeseries_window(
        series="PoC Stack VI",
        experiment_id=None,
        uuid="run-uuid-001",
        group="Conditioning",
        channels=["Stack Voltage"],
        visible_start_s=0,
        visible_end_s=7200,
        prefetch_margin_s=900,
        resolution="auto",
    )

    query = captured["query"]
    assert captured["key_prefix"] == "co_reporting_query"
    assert "FROM ps_xplatform_dev.co2elyd_dev.gold_timeseries" in query
    assert "series = 'PoC Stack VI'" in query
    assert "experiment_id =" not in query
    assert "uuid = 'run-uuid-001'" in query
    assert "`group` = 'Conditioning'" in query
    assert "std_channel IN ('Stack Voltage')" in query
    assert "std_channel AS channel_name" in query
    assert payload["meta"]["uuid"] == "run-uuid-001"
    assert payload["meta"]["group"] == "Conditioning"
    assert payload["meta"]["returned_points"] == 1


def test_co_reporting_query_rejects_missing_identity():
    with pytest.raises(ValueError, match="experiment_id or both uuid and group"):
        co_reporting_service.query_timeseries_window(
            series="PoC Stack VI",
            experiment_id=None,
            channels=["Stack Voltage"],
            visible_start_s=0,
            visible_end_s=60,
        )
