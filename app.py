import os
import dash
from dash import html, dcc, page_container
import dash_bootstrap_components as dbc
from dash_auth import OIDCAuth

external_stylesheets = [dbc.themes.BOOTSTRAP]

app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=external_stylesheets,
    suppress_callback_exceptions=True,
    pages_folder="spaces"
)

# OIDC Authentication setup
auth = OIDCAuth(app, secret_key=os.getenv("FLASK_SECRET_KEY", "dev"))
auth.register_provider(
    "azure",
    token_endpoint_auth_method="client_secret_post",
    client_id=os.getenv("AZURE_CLIENT_ID"),
    client_secret=os.getenv("AZURE_CLIENT_SECRET"),
    server_metadata_url=f'https://login.microsoftonline.com/{os.getenv("AZURE_TENANT_ID")}/v2.0/.well-known/openid-configuration',
)

app.layout = html.Div([
    html.Div("Header goes here"),
    html.Div("Sidebar goes here"),
    page_container,
    html.Div("Footer goes here"),
])

if __name__ == "__main__":
    app.run(debug=True, port=8501)