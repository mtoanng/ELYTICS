import os
import dash

from components.appshell import create_appshell
from services.auth import OIDCAuthWithToken

import redis
from flask_session import Session

from dotenv import load_dotenv
from waitress import serve
load_dotenv()

app = dash.Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    pages_folder="spaces",
    prevent_initial_callbacks=True,
    update_title=None
)

app.server.config["SESSION_TYPE"] = "redis"
app.server.config["SESSION_REDIS"] = redis.StrictRedis()
app.server.config["SESSION_PERMANENT"] = False
app.server.config["PREFERRED_URL_SCHEME"] = "https"
Session(app.server)

auth = OIDCAuthWithToken(app, secret_key=os.getenv("FRONTEND_OIDC_SECRET_KEY", "dev"))
auth.register_provider(
    "azure",
    token_endpoint_auth_method="client_secret_post",
    client_id=os.getenv("FRONTEND_AZURE_CLIENT_ID"),
    client_secret=os.getenv("FRONTEND_AZURE_CLIENT_SECRET"),
    server_metadata_url=f'https://login.microsoftonline.com/{os.getenv("FRONTEND_AZURE_TENANT_ID")}/v2.0/.well-known/openid-configuration',
    scope=f"openid profile email api://{os.getenv('BACKEND_AZURE_CLIENT_ID')}/user_impersonation"
)

app.layout = create_appshell()

if __name__ == "__main__":
    debug_mode = os.getenv("ENV", "development") == "development"
    if debug_mode:
        app.run(debug=True, host="0.0.0.0", port=8501, use_reloader=True)
    else:
        serve(app.server, host="0.0.0.0", port=8501, 
              trusted_proxy="*", 
              trusted_proxy_count=1)