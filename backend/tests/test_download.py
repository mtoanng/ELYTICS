import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from backend.internal.auth import verify_oidc_token
from backend.main import app


@pytest.fixture
def client():
    app.dependency_overrides[verify_oidc_token] = lambda: {
        "groups": ["IdM2BCD_holmes_pemely_user"],
        "email": "test@example.com",
    }
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_trigger_download_unknown_route(client):
    response = client.post("/api/sherlock/download/nonexistent_table")
    assert response.status_code == 404


def test_trigger_download_unconfigured_service(client, monkeypatch):
    import backend.routers.download as dl
    monkeypatch.setattr(dl, "DATABRICKS_WORKSPACE_URL", "")
    response = client.post("/api/sherlock/download/ccm")
    assert response.status_code == 503


def test_trigger_download_calls_databricks(client, monkeypatch):
    import backend.routers.download as dl
    monkeypatch.setattr(dl, "DATABRICKS_WORKSPACE_URL", "https://fake.azuredatabricks.net")
    monkeypatch.setattr(dl, "DATABRICKS_EXPORT_JOB_ID", "42")
    monkeypatch.setattr(dl, "DATABRICKS_TOKEN", "token")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"run_id": 99}

    with patch("backend.routers.download.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        response = client.post("/api/sherlock/download/ccm")

    assert response.status_code == 200
    assert response.json()["run_id"] == 99
    assert response.json()["status"] == "running"


def test_download_status_running(client, monkeypatch):
    import backend.routers.download as dl
    monkeypatch.setattr(dl, "DATABRICKS_WORKSPACE_URL", "https://fake.azuredatabricks.net")
    monkeypatch.setattr(dl, "DATABRICKS_TOKEN", "token")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"state": {"life_cycle_state": "RUNNING", "result_state": ""}}

    with patch("backend.routers.download.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        response = client.get("/api/sherlock/download/status/99")

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["url"] is None
