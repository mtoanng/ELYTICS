import os
import dash
from dash import html, dcc, Output, Input, State
from dash import callback_context
import dash_bootstrap_components as dbc
from dash_auth import OIDCAuth

from components import header, sidebar, footer

from dotenv import load_dotenv
from waitress import serve
load_dotenv()

external_stylesheets = [dbc.themes.BOOTSTRAP]

app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=external_stylesheets,
    suppress_callback_exceptions=True,
    pages_folder="spaces"
)

auth = OIDCAuth(app, secret_key=os.getenv("OIDC_SECRET_KEY", "dev"))
auth.register_provider(
    "azure",
    token_endpoint_auth_method="client_secret_post",
    client_id=os.getenv("AZURE_CLIENT_ID"),
    client_secret=os.getenv("AZURE_CLIENT_SECRET"),
    server_metadata_url=f'https://login.microsoftonline.com/{os.getenv("AZURE_TENANT_ID")}/v2.0/.well-known/openid-configuration',
)

app.layout = html.Div([
    html.Div(header.layout(), id="header-container", className="light-mode"),
    html.Div(sidebar.layout(), id="sidebar-container", className="light-mode"),
    html.Div([
        html.Div(style={"height": "70px"}),  # Spacer for header height
        dash.page_container
    ], id="page-content", className="page-content"),
    footer.layout(),
    dcc.Store(id="sidebar-state", data={"collapsed": False}),
    dcc.Store(id="theme-store", data="light"),
    dcc.Store(id="theme-body-store", data="light"),
    dcc.Store(id="table-redraw-trigger", data=None),
    dcc.Interval(id="table-resize-interval", interval=500, n_intervals=0, max_intervals=1, disabled=True),
    # Clientside callback to set the body class for dark/light mode
    app.clientside_callback(
        "function(theme) {\n" +
        "  if (theme && document && document.body) {\n" +
        "    document.body.classList.remove('dark-mode', 'light-mode');\n" +
        "    document.body.classList.add(theme + '-mode');\n" +
        "  }\n" +
        "  return window.dash_clientside.no_update;\n" +
        "}",
        Output("theme-body-store", "data"),
        Input("theme-store", "data")
    )
])

# Corrected callback: includes table-redraw-trigger in State, and matches argument order
@app.callback(
    [
        Output("sidebar", "className"),
        Output("page-content", "className"),
        Output("sidebar-state", "data"),
        Output("sidebar-toggle-icon", "className"),
        Output("table-resize-interval", "disabled"),
        Output("table-resize-interval", "n_intervals"),
        Output("header-container", "className"),
        Output("sidebar-container", "className"),
    ],
    [Input("sidebar-toggle", "n_clicks"), Input("theme-switch", "value")],
    [State("sidebar-state", "data"), State("table-redraw-trigger", "data"), State("theme-store", "data")]
)
def merged_sidebar_and_resize(n, theme_switch, state, table_redraw, theme_store):
    ctx = callback_context
    # Defaults for sidebar
    collapsed = state["collapsed"]
    # Theme logic
    theme = "dark" if theme_switch else "light"
    sidebar_class = f"sidebar {'sidebar-collapsed' if collapsed else ''} {theme}-mode".strip()
    if collapsed:
        content_class = f"page-content page-content-expanded {theme}-mode"
    else:
        content_class = f"page-content {theme}-mode"
    icon_class = "bi bi-arrow-right-short" if collapsed else "bi bi-arrow-left-short"
    header_class = f"{theme}-mode"
    # Defaults for interval
    interval_disabled = True
    interval_n = 0

    if ctx.triggered:
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == "sidebar-toggle":
            if n:
                collapsed = not collapsed
            sidebar_class = "sidebar sidebar-collapsed" if collapsed else "sidebar"
            theme = "dark" if theme_switch else "light"
            if collapsed:
                content_class = f"page-content page-content-expanded {theme}-mode"
            else:
                content_class = f"page-content {theme}-mode"
            icon_class = "bi bi-arrow-right-short" if collapsed else "bi bi-arrow-left-short"
            interval_disabled = False
            interval_n = 0
    return sidebar_class, content_class, {"collapsed": collapsed}, icon_class, interval_disabled, interval_n, header_class, sidebar_class

# Callback to store theme selection
@app.callback(
    Output("theme-store", "data"),
    Input("theme-switch", "value")
)
def update_theme_store(theme_switch):
    return "dark" if theme_switch else "light"

# Clientside callback to trigger window resize event for DataTable realignment
app.clientside_callback(
    "function(n_intervals) { window.dispatchEvent(new Event('resize')); return window.dash_clientside.no_update; }",
    Output("table-resize-interval", "max_intervals"),
    Input("table-resize-interval", "n_intervals"),
    prevent_initial_call=True
)

# Management group toggle
@app.callback(
    Output("management-group-collapse", "is_open"),
    Output("management-group-icon", "className"),
    Input("management-group-toggle", "n_clicks"),
    State("management-group-collapse", "is_open"),
)
def toggle_management_group(n, is_open):
    if n:
        new_state = not is_open
        icon_class = "bi bi-chevron-down me-2" if new_state else "bi bi-chevron-right me-2"
        return new_state, icon_class
    return is_open, "bi bi-chevron-right me-2"


@app.callback(
    [Output("explore-group-collapse", "is_open"),
     Output("explore-group-icon", "className")],
    [Input("explore-group-toggle", "n_clicks")],
    [State("explore-group-collapse", "is_open")]
)
def toggle_explore_group(n, is_open):
    if n:
        new_state = not is_open
        icon_class = "bi bi-chevron-down me-2" if new_state else "bi bi-chevron-right me-2"
        return new_state, icon_class
    return is_open, "bi bi-chevron-right me-2"

@app.callback(
    [Output("data-group-collapse", "is_open"),
     Output("data-group-icon", "className")],
    [Input("data-group-toggle", "n_clicks")],
    [State("data-group-collapse", "is_open")]
)
def toggle_data_group(n, is_open):
    if n:
        new_state = not is_open
        icon_class = "bi bi-chevron-down me-2" if new_state else "bi bi-chevron-right me-2"
        return new_state, icon_class
    return is_open, "bi bi-chevron-right me-2"

@app.callback(
    [Output("ai-group-collapse", "is_open"),
     Output("ai-group-icon", "className")],
    [Input("ai-group-toggle", "n_clicks")],
    [State("ai-group-collapse", "is_open")]
)
def toggle_ai_group(n, is_open):
    if n:
        new_state = not is_open
        icon_class = "bi bi-chevron-down me-2" if new_state else "bi bi-chevron-right me-2"
        return new_state, icon_class
    return is_open, "bi bi-chevron-right me-2"

if __name__ == "__main__":
    debug_mode = os.getenv("ENVIRONMENT", "development") == "development"
    if debug_mode:
        app.run(debug=True, port=8501, use_reloader=True)
    else:
        serve(app.server, host="0.0.0.0", port=8501)