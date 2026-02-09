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

            if self.log_signins:
                import logging
                logging.info("User %s is logging in.", filtered_user.get("email"))

        return redirect(self.app.config.get("url_base_pathname") or "/")