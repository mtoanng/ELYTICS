import requests
import os
import json
import pandas as pd
from flask import session
from typing import Any, Dict, List, Optional
from datetime import datetime

API_BASE = os.environ.get("BACKEND_API_URL", "http://localhost:8000")

def get_api_headers():
    """Extract OIDC token from Flask session and return headers"""
    token = session.get("access_token")
    if not token:
        print(f"[DEBUG] Session keys: {list(session.keys())}")
        print(f"[DEBUG] access_token present: {('access_token' in session)}")
        raise ValueError("No OIDC token available in session")
    
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

def get_metadata(space: str, route_name: str) -> List[Dict[str, Any]]:
    """
    Fetch metadata (distinct values for filter columns) from the backend.
    Metadata endpoints return all distinct values for a table's columns.
    """
    headers = get_api_headers()
    url = f"{API_BASE}/api/{space}/metadata/{route_name}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
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
    headers = get_api_headers()
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
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
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
    headers = get_api_headers()
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
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    payload = response.json()
    
    # Parse the response which includes data and metadata
    data = payload.get("data", [])
    meta = payload.get("meta", {})
    
    df = pd.DataFrame(data)
    # Attach metadata for reference (e.g., bucket_seconds, returned_points)
    df.attrs["meta"] = meta
    return df

def get_table_as_df(space: str, route_name: str, data_kind: str = "data") -> pd.DataFrame:
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
    headers = get_api_headers()
    url = f"{API_BASE}/api/system/table-stats"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()