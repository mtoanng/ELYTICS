import pytest

import backend.services.databricks as databricks_service


def test_build_engine_uses_azure_service_principal_auth(monkeypatch):
    captured = {}

    def fake_create_engine(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(databricks_service, "create_engine", fake_create_engine)
    monkeypatch.setattr(databricks_service, "DATABRICKS_SERVER_HOSTNAME", "adb.example.azuredatabricks.net")
    monkeypatch.setattr(databricks_service, "DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/demo")
    monkeypatch.setattr(databricks_service, "DATABRICKS_AZURE_CLIENT_ID", "client-id")
    monkeypatch.setattr(databricks_service, "DATABRICKS_AZURE_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(databricks_service, "DATABRICKS_AZURE_TENANT_ID", "tenant-id")
    monkeypatch.setattr(databricks_service, "DATABRICKS_AZURE_WORKSPACE_RESOURCE_ID", "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Databricks/workspaces/ws")
    monkeypatch.setattr(databricks_service, "_AUTH_TYPE", "azure-sp-m2m")

    databricks_service._build_engine()

    assert captured["args"] == ("databricks://",)
    connect_args = captured["kwargs"]["connect_args"]
    assert connect_args == {
        "server_hostname": "adb.example.azuredatabricks.net",
        "http_path": "/sql/1.0/warehouses/demo",
        "auth_type": "azure-sp-m2m",
        "azure_client_id": "client-id",
        "azure_client_secret": "client-secret",
        "azure_tenant_id": "tenant-id",
        "azure_workspace_resource_id": "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Databricks/workspaces/ws",
    }
    assert captured["kwargs"]["pool_size"] == databricks_service._POOL_SIZE
    assert captured["kwargs"]["max_overflow"] == databricks_service._MAX_OVERFLOW


def test_build_engine_requires_service_principal_secret(monkeypatch):
    monkeypatch.setattr(databricks_service, "DATABRICKS_SERVER_HOSTNAME", "adb.example.azuredatabricks.net")
    monkeypatch.setattr(databricks_service, "DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/demo")
    monkeypatch.setattr(databricks_service, "DATABRICKS_AZURE_CLIENT_ID", "client-id")
    monkeypatch.setattr(databricks_service, "DATABRICKS_AZURE_CLIENT_SECRET", None)
    monkeypatch.setattr(databricks_service, "_AUTH_TYPE", "azure-sp-m2m")

    with pytest.raises(RuntimeError, match="DATABRICKS_AZURE_CLIENT_SECRET"):
        databricks_service._build_engine()
