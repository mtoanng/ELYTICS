# Template -> TODO: implement this functionality

import os

import httpx
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException

from backend.internal.auth import require_groups
from backend.internal.config_types import TabularConfig, TimeseriesConfig, MetadataConfig
from backend.internal.util import fully_qualified_view

import backend.config.sherlock as sherlock
import backend.config.watson as watson
import backend.config.enola as enola
import backend.config.mycroft as mycroft

router = APIRouter(tags=["Download"])

DATABRICKS_WORKSPACE_URL = os.environ.get("DATABRICKS_WORKSPACE_URL", "")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "")
DATABRICKS_EXPORT_JOB_ID = os.environ.get("DATABRICKS_EXPORT_JOB_ID", "")
AZURE_STORAGE_ACCOUNT_NAME = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", "")
AZURE_STORAGE_ACCOUNT_KEY = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY", "")
AZURE_STORAGE_CONTAINER_NAME = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "exports")

_ALL_CONFIGS: dict[str, dict[str, list]] = {
    "sherlock": {"tabular": sherlock.TABULAR_CONFIG, "timeseries": sherlock.TIMESERIES_CONFIG, "metadata": sherlock.METADATA_CONFIG},
    "watson":   {"tabular": watson.TABULAR_CONFIG,   "timeseries": watson.TIMESERIES_CONFIG,   "metadata": watson.METADATA_CONFIG},
    "enola":    {"tabular": enola.TABULAR_CONFIG,     "timeseries": enola.TIMESERIES_CONFIG,     "metadata": enola.METADATA_CONFIG},
    "mycroft":  {"tabular": mycroft.TABULAR_CONFIG,   "timeseries": mycroft.TIMESERIES_CONFIG,   "metadata": mycroft.METADATA_CONFIG},
}


def _find_config(space: str, route_name: str) -> TabularConfig | TimeseriesConfig | MetadataConfig | None:
    for _type, cfgs in _ALL_CONFIGS.get(space, {}).items():
        for cfg in cfgs:
            if cfg.route_name == route_name:
                return cfg
    return None


def _databricks_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {DATABRICKS_TOKEN}", "Content-Type": "application/json"}


@router.post("/api/{space}/download/{route_name}", summary="Trigger export job")
async def trigger_download(space: str, route_name: str):
    cfg = _find_config(space, route_name)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"No route '{route_name}' in space '{space}'")
    if not DATABRICKS_WORKSPACE_URL or not DATABRICKS_EXPORT_JOB_ID:
        raise HTTPException(status_code=503, detail="Download service not configured")

    data_kind = "data" if isinstance(cfg, (TabularConfig, TimeseriesConfig)) else "metadata"
    view_name = fully_qualified_view(space=space, data_kind=data_kind, table_name=cfg.table_name)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DATABRICKS_WORKSPACE_URL}/api/2.1/jobs/run-now",
            headers=_databricks_headers(),
            json={"job_id": int(DATABRICKS_EXPORT_JOB_ID), "notebook_params": {"view_name": view_name}},
            timeout=30,
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Databricks error: {resp.text}")

    run_id = resp.json().get("run_id")
    return {"run_id": run_id, "status": "running"}


@router.get("/api/{space}/download/status/{run_id}", summary="Poll export job status")
async def get_download_status(space: str, run_id: int):
    if not DATABRICKS_WORKSPACE_URL:
        raise HTTPException(status_code=503, detail="Download service not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DATABRICKS_WORKSPACE_URL}/api/2.1/jobs/runs/get",
            headers=_databricks_headers(),
            params={"run_id": run_id},
            timeout=30,
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Databricks error: {resp.text}")

    body = resp.json()
    life_cycle = body.get("state", {}).get("life_cycle_state", "")
    result_state = body.get("state", {}).get("result_state", "")

    if life_cycle != "TERMINATED":
        return {"status": "running", "url": None, "error": None}

    if result_state != "SUCCESS":
        return {"status": "failed", "url": None, "error": body.get("state", {}).get("state_message")}

    if not AZURE_STORAGE_ACCOUNT_NAME or not AZURE_STORAGE_ACCOUNT_KEY:
        raise HTTPException(status_code=503, detail="Storage not configured")

    blob_name = f"{run_id}.csv"
    sas_token = generate_blob_sas(
        account_name=AZURE_STORAGE_ACCOUNT_NAME,
        container_name=AZURE_STORAGE_CONTAINER_NAME,
        blob_name=blob_name,
        account_key=AZURE_STORAGE_ACCOUNT_KEY,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    url = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_STORAGE_CONTAINER_NAME}/{blob_name}?{sas_token}"
    return {"status": "complete", "url": url, "error": None}
