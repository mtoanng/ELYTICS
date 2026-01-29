
from dash import html, dcc
import dash_bootstrap_components as dbc
from services.changelog_service import get_latest_released_version

# TODO: implement use of dash_auth.list_groups to conditionally show/hide sidebar items

def get_sidebar():
    latest_version = get_latest_released_version() or "Unknown"
    return html.Div(
        [
            html.Div(
                [
                    dbc.NavLink([
                        html.Span(f"Version {latest_version}", style={"fontSize": "0.85em", "fontWeight": "normal"})
                    ], href="/version_history", active="exact", className="ps-2", style={"marginBottom": "0.25rem", "marginTop": "0.5rem", "textAlign": "left"}),
                    html.Hr(),
                    dbc.Nav(
                        [
                            dbc.NavLink("Main", href="/", active="exact"),
                        ],
                        vertical=True,
                        pills=True,
                    ),
                    html.Hr(),

                    # Management group
                    dbc.Button(
                        [html.I(className="bi bi-chevron-right me-2", id="management-group-icon"), "Management"],
                        id="management-group-toggle",
                        className="sidebar-group-btn",
                        color="link",
                        style={"textAlign": "left", "width": "100%"},
                    ),
                    dbc.Collapse(
                        dbc.Nav(
                            [
                                dbc.NavLink("Testrig Overview", href="/management/management", active="exact", className="ps-4"),
                                dbc.NavLink("Timeseries Tester", href="/management/timeseries", active="exact", className="ps-4"),
                            ],
                            vertical=True,
                            pills=True,
                        ),
                        id="management-group-collapse",
                        is_open=False,
                    ),

                    html.Hr(),


                    # Data Exploration group
                    dbc.Button(
                        [html.I(className="bi bi-chevron-right me-2", id="explore-group-icon"), "Data Exploration"],
                        id="explore-group-toggle",
                        className="sidebar-group-btn",
                        color="link",
                        style={"textAlign": "left", "width": "100%"},
                    ),
                    dbc.Collapse(
                        dbc.Nav(
                            [
                                dbc.NavLink("Order Overview", href="/explore/order", active="exact", className="ps-4"),
                                dbc.NavLink("Sample Overview", href="/explore/sample", active="exact", className="ps-4"),
                                dbc.NavLink("CCM Overview", href="/explore/ccm", active="exact", className="ps-4"),
                                dbc.NavLink("Polarization Curves", href="/explore/polcurves", active="exact", className="ps-4"),
                            ],
                            vertical=True,
                            pills=True,
                        ),
                        id="explore-group-collapse",
                        is_open=False,
                    ),

                    # Data Analysis group
                    dbc.Button(
                        [html.I(className="bi bi-chevron-right me-2", id="data-group-icon"), "Data Analysis"],
                        id="data-group-toggle",
                        className="sidebar-group-btn",
                        color="link",
                        style={"textAlign": "left", "width": "100%"},
                    ),
                    dbc.Collapse(
                        dbc.Nav(
                            [
                                dbc.NavLink("Summary Stats", href="/analysis/summary", active="exact", className="ps-4"),
                                dbc.NavLink("Charts", href="/analysis/charts", active="exact", className="ps-4"),
                            ],
                            vertical=True,
                            pills=True,
                        ),
                        id="data-group-collapse",
                        is_open=False,
                    ),

                    # AI/ML group
                    dbc.Button(
                        [html.I(className="bi bi-chevron-right me-2", id="ai-group-icon"), "AI/ML"],
                        id="ai-group-toggle",
                        className="sidebar-group-btn",
                        color="link",
                        style={"textAlign": "left", "width": "100%"},
                    ),
                    dbc.Collapse(
                        dbc.Nav(
                            [
                                dbc.NavLink("Model Overview", href="/ai/model", active="exact", className="ps-4"),
                                dbc.NavLink("Predictions", href="/ai/predictions", active="exact", className="ps-4"),
                            ],
                            vertical=True,
                            pills=True,
                        ),
                        id="ai-group-collapse",
                        is_open=False,
                    ),
                    html.Hr(),
                ],
                id="sidebar",
                className="sidebar",
            ),
            dbc.Button(
                id="sidebar-toggle",
                color="secondary",
                className="sidebar-toggle-btn",
                n_clicks=0,
                outline=True,
                size="sm",
                style={"marginTop": 0},
                children=html.I(className="bi bi-arrow-left-short", id="sidebar-toggle-icon")
            ),
        ],
        className="sidebar-container"
    )
