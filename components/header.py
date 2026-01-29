from dash.dependencies import Input, Output
from dash import callback
from dash import html, dcc
import dash_bootstrap_components as dbc

# TODO: use dash_auth.list_groups to conditionally show available spaces in dropdown
# nice to have: show unavailable spaces wiht a tooltip saying they need _x oneidm role?

def header_layout():
    return html.Header([
        html.Div([
            # Left: Sherlock logo and text
            html.Div(
                [
                    dcc.Link(
                        html.Img(
                            src="/assets/sherlock_logo.png",
                            height="50px",
                            className="header-logo-left",
                            style={"cursor": "pointer"}
                        ),
                        href="/"
                    ),
                    html.Span(
                        "Sherlock",
                        className="header-title sherlock-green",
                        style={
                            "fontSize": "2rem",
                            "fontWeight": "bold",
                            "marginLeft": "1rem",
                            "letterSpacing": "0.04em",
                            "fontFamily": "Segoe UI, Arial, sans-serif",
                            "verticalAlign": "middle"
                        }
                    ),
                ],
                style={"display": "flex", "alignItems": "center"}
            ),
            # Center/right: theme switch group
            html.Div([
                html.I(className="bi bi-brightness-high", style={"fontSize": "22px", "color": "#f7c948", "marginRight": "8px"}),
                dbc.Switch(
                    id="theme-switch",
                    label=None,
                    value=False,
                    className="theme-switch-custom",
                    inputClassName="form-check-input",
                    style={"marginLeft": "0.5rem", "marginRight": "0.5rem"}
                ),
                html.I(className="bi bi-moon-fill", style={"fontSize": "22px", "color": "#f1f1f1", "marginLeft": "8px"}),
            ], style={"display": "flex", "alignItems": "center", "marginRight": "2rem", "marginLeft": "auto", "justifyContent": "flex-end"}),
            # Right: Bosch logo
            html.Div(
                id="bosch-logo-div",
                style={"display": "flex", "alignItems": "center"}
            ),
        ], style={"width": "100%", "display": "flex", "alignItems": "center", "justifyContent": "space-between"}),
    ], className="header-bar")

layout = header_layout

@callback(
    Output("bosch-logo-div", "children"),
    Input("theme-store", "data")
)
def update_bosch_logo(theme):
    if theme == "dark":
        logo_src = "/assets/Bosch_symbol_logo_black.png"
        class_name = "header-logo-right invert-logo"
    else:
        logo_src = "/assets/Bosch_symbol_logo_black_red.png"
        class_name = "header-logo-right"
    return html.Img(
        src=logo_src,
        height="50px",
        className=class_name
    )