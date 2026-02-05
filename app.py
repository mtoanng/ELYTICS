import os
import dash
from dash_auth import OIDCAuth

from components.appshell import create_appshell

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

auth = OIDCAuth(app, secret_key=os.getenv("OIDC_SECRET_KEY", "dev"))
auth.register_provider(
    "azure",
    token_endpoint_auth_method="client_secret_post",
    client_id=os.getenv("AZURE_CLIENT_ID"),
    client_secret=os.getenv("AZURE_CLIENT_SECRET"),
    server_metadata_url=f'https://login.microsoftonline.com/{os.getenv("AZURE_TENANT_ID")}/v2.0/.well-known-openid-configuration',
)

app.layout = create_appshell()

if __name__ == "__main__":
    debug_mode = os.getenv("ENV", "development") == "development"
    if debug_mode:
        app.run(debug=True, host="0.0.0.0", port=8501, use_reloader=True)
    else:
        serve(app.server, host="0.0.0.0", port=8501)