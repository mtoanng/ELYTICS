import jwt
import time
import os
import requests
from dash_auth.oidc_auth import OIDCAuth
from flask import session, redirect

# Custom OIDCAuth class to store tokens in session
class OIDCAuthWithToken(OIDCAuth):
    def callback(self, idp: str):
        if idp not in self.oauth._registry:
            return f"'{idp}' is not a valid registered idp", 400

        oauth_client = self.get_oauth_client(idp)
        oauth_kwargs = self.get_oauth_kwargs(idp)
        try:
            token = oauth_client.authorize_access_token(
                **oauth_kwargs.get("authorize_token_kwargs", {}),
            )
        except Exception as err:
            return str(err), 401

        user = token.get("userinfo")
        if user:
            filtered_user = {
                "email": user.get("email"),
                "groups": [g for g in user.get("groups", []) if g.startswith("IdM2BCD_holmes_pemely_")]
            }
            session["user"] = filtered_user
            session["idp"] = idp

            if "access_token" in token:
                session["access_token"] = token["access_token"]
            if "refresh_token" in token:
                session["refresh_token"] = token["refresh_token"]

            if self.log_signins:
                import logging
                logging.info("User %s is logging in.", filtered_user.get("email"))

        return redirect(self.app.config.get("url_base_pathname") or "/")

# Helper functions to check if access token is expired
def _is_access_token_expired():
    token = session.get("access_token")
    if not token:
        return True
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get("exp", 0)
        return exp < int(time.time())
    except Exception:
        return True


def _refresh_access_token():
    """Attempt to get a new access token using the stored refresh token.
    Returns True if successful, False otherwise."""
    refresh_token = session.get("refresh_token")
    if not refresh_token:
        return False
    try:
        tenant_id = os.getenv("FRONTEND_AZURE_TENANT_ID")
        client_id = os.getenv("FRONTEND_AZURE_CLIENT_ID")
        client_secret = os.getenv("FRONTEND_AZURE_CLIENT_SECRET")
        backend_client_id = os.getenv("BACKEND_AZURE_CLIENT_ID")
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "scope": f"openid profile email offline_access api://{backend_client_id}/user_impersonation",
        }
        response = requests.post(token_url, data=data, timeout=10)
        if response.status_code == 200:
            new_token = response.json()
            if "access_token" in new_token:
                session["access_token"] = new_token["access_token"]
            if "refresh_token" in new_token:
                session["refresh_token"] = new_token["refresh_token"]
            return True
        return False
    except Exception:
        return False


def check_access(groups=None):
    """
    Check if user has access based on groups. 
    Returns (has_access, user, needs_login)
    - has_access: True if user has required access
    - user: User dict or None
    - needs_login: True if token expired and needs re-authentication
    """
    if _is_access_token_expired():
        if not _refresh_access_token():
            session.clear()
            return False, None, True
    
    user = session.get("user")
    if not user:
        return False, None, True
    
    if groups and not any(g in user.get("groups", []) for g in groups):
        return False, user, False
    
    return True, user, False