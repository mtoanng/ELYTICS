import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

API_BASE = os.environ.get("BACKEND_API_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = 125


def get_api_headers():
    return {"Content-Type": "application/json"}


def _get_with_token_refresh(url: str, params: dict | None = None) -> requests.Response:
    response = requests.get(
        url,
        params=params,
        headers=get_api_headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response


def _post_with_token_refresh(url: str, payload: dict | None = None) -> requests.Response:
    response = requests.post(
        url,
        json=payload,
        headers=get_api_headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response


def get_metadata(space: str, route_name: str) -> List[Dict[str, Any]]:
    """
    Fetch metadata (distinct values for filter columns) from the backend.
    Metadata endpoints return all distinct values for a table's columns.
    """
    url = f"{API_BASE}/api/{space}/metadata/{route_name}"
    response = _get_with_token_refresh(url)
    return response.json().get("data", [])


def get_tabular(
    space: str,
    route_name: str,
    filters: Optional[Dict[str, Any]] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
) -> pd.DataFrame:
    """
    Fetch tabular data from the backend.
    Returns the full filtered dataset as a pandas DataFrame.

    Args:
        space: The space name (e.g., 'sherlock')
        route_name: The tabular route name (e.g., 'order', 'polcurve')
        filters: Dict of filter column -> value(s). Values can be strings or lists.
        sort_by: Column name to sort by
        sort_dir: Sort direction ('asc' or 'desc')
    """
    params = {}

    # Add filters as query params
    if filters:
        for key, value in filters.items():
            if isinstance(value, list):
                params[key] = value
            else:
                params[key] = str(value)

    # Add sort parameters if provided
    if sort_by:
        params["sort_by"] = sort_by
        params["sort_dir"] = sort_dir

    url = f"{API_BASE}/api/{space}/tabular/{route_name}"
    response = _get_with_token_refresh(url, params=params)
    data = response.json().get("data", [])
    return pd.DataFrame(data)


def get_timeseries(
    space: str,
    route_name: str,
    start: datetime | str | None,
    end: datetime | str | None,
    columns: List[str],
    time_column: str = "time",
    target_points: int = 1200,
    filters: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Fetch timeseries data from the backend with automatic bucketing.

    Args:
        space: The space name (e.g., 'sherlock')
        route_name: The timeseries route name (e.g., 'timeseries_exp')
        start: Optional start datetime (backend infers from filters when omitted)
        end: Optional end datetime (backend infers from filters when omitted)
        columns: List of column names to fetch
        time_column: Name of the time column in the dataset
        target_points: Target number of buckets (~1200 is good default)
        filters: Dict of filter column -> value(s) including required filters like order_id
    """
    params = {
        "time_column": time_column,
        "target_points": target_points,
    }

    if start is not None:
        params["start"] = start.isoformat() if isinstance(start, datetime) else start
    if end is not None:
        params["end"] = end.isoformat() if isinstance(end, datetime) else end

    # Add columns as separate query params
    if columns:
        params["columns"] = columns

    # Add filters including required ones
    if filters:
        for key, value in filters.items():
            if isinstance(value, list):
                params[key] = value
            else:
                params[key] = str(value)

    url = f"{API_BASE}/api/{space}/timeseries/{route_name}"
    response = _get_with_token_refresh(url, params=params)
    payload = response.json()

    # Parse the response which includes data and metadata
    data = payload.get("data", [])
    meta = payload.get("meta", {})

    df = pd.DataFrame(data)
    # Attach metadata for reference (e.g., bucket_seconds, returned_points)
    df.attrs["meta"] = meta
    return df


def get_co_reporting_series() -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/elytics/co-reporting/series"
    response = _get_with_token_refresh(url)
    return response.json().get("data", [])


def _co_reporting_identity_params(
    series: str,
    experiment_id: int | None = None,
    uuid: str | None = None,
    group: str | None = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"series": series}
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
) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/elytics/co-reporting/channels"
    response = _get_with_token_refresh(
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
    channels: List[str],
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
    params.update({
        "channels": channels,
        "resolution": resolution,
    })
    url = f"{API_BASE}/api/elytics/co-reporting/timeseries"
    response = _get_with_token_refresh(url, params=params)
    return pd.DataFrame(response.json().get("data", []))


def query_co_reporting_timeseries(
    series: str,
    experiment_id: int | None,
    channels: List[str],
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
    payload.update({
        "channels": channels,
        "visible_start_s": visible_start_s,
        "visible_end_s": visible_end_s,
        "resolution": resolution,
    })
    if prefetch_margin_s is not None:
        payload["prefetch_margin_s"] = prefetch_margin_s
    if mode is not None:
        payload["mode"] = mode
    if report_id is not None:
        payload["report_id"] = report_id
    if include_band is not None:
        payload["include_band"] = include_band

    url = f"{API_BASE}/api/elytics/co-reporting/query"
    response = _post_with_token_refresh(url, payload=payload)
    payload = response.json()
    df = pd.DataFrame(payload.get("data", []))
    df.attrs["meta"] = payload.get("meta", {})
    return df


def get_table_as_df(
    space: str, route_name: str, data_kind: str = "data"
) -> pd.DataFrame:
    """
    Backward compatibility wrapper.
    Maps old get_table_as_df calls to new tabular/metadata endpoints.
    """
    if data_kind == "data":
        return get_tabular(space, route_name)
    else:
        data = get_metadata(space, route_name)
        return pd.DataFrame(data)


def get_table_stats():
    """Fetch system table statistics from the backend."""
    url = f"{API_BASE}/api/system/table-stats"
    response = _get_with_token_refresh(url)
    return response.json()
