import requests
import os
from flask import session

API_BASE = os.environ.get("API_URL", "http://localhost:8000")

def get_api_headers():
    """Extract OIDC token from Flask session and return headers"""
    # Get token from Flask session (set by dash_auth/OAuth)
    token = session.get("access_token")
    if not token:
        raise ValueError("No OIDC token available in session")
    
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

def get_latest_data(path):
    headers = get_api_headers()
    response = requests.get(f"{API_BASE}/{path}", headers=headers)
    response.raise_for_status()
    return response.json()