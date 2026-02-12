import jwt
import time
from dash_auth.oidc_auth import OIDCAuth
from flask import session, redirect, request

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
    
def check_access(groups=None):
    """Check if user has access based on groups. Returns (has_access, user)"""
    if _is_access_token_expired():
        return False, None
    user = session.get("user")
    if not user:
        return False, None
    if groups and not any(g in user.get("groups", []) for g in groups):
        return False, user
    return True, user