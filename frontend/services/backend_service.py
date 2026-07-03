import os
from typing import Any

import pandas as pd
import requests

API_BASE = os.environ.get("BACKEND_API_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = 125


def get_api_headers() -> dict[str, str]:
    return {"Content-Type": "application/json"}


def _get(url: str, params: dict[str, Any] | None = None) -> requests.Response:
    response = requests.get(
        url,
        params=params,
        headers=get_api_headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response


def _post(url: str, payload: dict[str, Any] | None = None) -> requests.Response:
    response = requests.post(
        url,
        json=payload,
        headers=get_api_headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response


def get_co_reporting_series() -> list[dict[str, Any]]:
    url = f"{API_BASE}/api/elytics/co-reporting/series"
    response = _get(url)
    return response.json().get("data", [])


def _co_reporting_identity_params(
    series: str,
    experiment_id: int | None = None,
    uuid: str | None = None,
    group: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"series": series}
    if experiment_id is not None:
        params["experiment_id"] = experiment_id
    if uuid:
        params["uuid"] = uuid
    if group:
        params["group"] = group
    return params


def get_co_reporting_channels(
    series: str,
    experiment_id: int | None = None,
    uuid: str | None = None,
    group: str | None = None,
) -> list[dict[str, Any]]:
    url = f"{API_BASE}/api/elytics/co-reporting/channels"
    response = _get(
        url,
        params=_co_reporting_identity_params(
            series=series,
            experiment_id=experiment_id,
            uuid=uuid,
            group=group,
        ),
    )
    return response.json().get("data", [])


def get_co_reporting_timeseries(
    series: str,
    experiment_id: int | None,
    channels: list[str],
    resolution: str = "agg",
    uuid: str | None = None,
    group: str | None = None,
) -> pd.DataFrame:
    params = _co_reporting_identity_params(
        series=series,
        experiment_id=experiment_id,
        uuid=uuid,
        group=group,
    )
    params.update({"channels": channels, "resolution": resolution})
    url = f"{API_BASE}/api/elytics/co-reporting/timeseries"
    response = _get(url, params=params)
    return pd.DataFrame(response.json().get("data", []))


def query_co_reporting_timeseries(
    series: str,
    experiment_id: int | None,
    channels: list[str],
    visible_start_s: float,
    visible_end_s: float,
    prefetch_margin_s: float | None = None,
    resolution: str = "auto",
    mode: str | None = None,
    report_id: str | None = None,
    include_band: bool | None = None,
    uuid: str | None = None,
    group: str | None = None,
) -> pd.DataFrame:
    payload = _co_reporting_identity_params(
        series=series,
        experiment_id=experiment_id,
        uuid=uuid,
        group=group,
    )
    payload.update(
        {
            "channels": channels,
            "visible_start_s": visible_start_s,
            "visible_end_s": visible_end_s,
            "resolution": resolution,
        }
    )
    if prefetch_margin_s is not None:
        payload["prefetch_margin_s"] = prefetch_margin_s
    if mode is not None:
        payload["mode"] = mode
    if report_id is not None:
        payload["report_id"] = report_id
    if include_band is not None:
        payload["include_band"] = include_band

    url = f"{API_BASE}/api/elytics/co-reporting/query"
    response = _post(url, payload=payload)
    body = response.json()
    df = pd.DataFrame(body.get("data", []))
    df.attrs["meta"] = body.get("meta", {})
    return df
