import requests
import os
import json
import pandas as pd
from flask import session

API_BASE = os.environ.get("BACKEND_API_URL", "http://localhost:8000")

def get_api_headers():
    """Extract OIDC token from Flask session and return headers"""
    token = session.get("access_token")
    if not token:
        raise ValueError("No OIDC token available in session")
    
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

def get_table_as_df(space, table_name, data_kind="data"):
    """
    Request a table from the backend and return as a pandas DataFrame.
    """
    headers = get_api_headers()
    url = f"{API_BASE}/api/{space}/tables/{data_kind}/{table_name}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json().get("data", [])
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = []
    return pd.DataFrame(data)