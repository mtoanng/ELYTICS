"""Elytics reporting app for the CO Energystack analytics workflow.

This module intentionally keeps the existing Dash reporting behavior while
running inside the current frontend shell. Authentication and legacy multi-space
chrome are omitted so the demo can focus on timeseries visualization and the
Databricks-backed reporting migration.
"""

import logging
import os

import dash_bootstrap_components as dbc
from dash import dcc, html

from .data_provider import ElyticsDataManager
from .tabs import custom_reports
from .tabs import standard_reports

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
    level=getattr(logging, os.getenv("DASH_LOG_LEVEL", "INFO").upper(), logging.INFO),
)

data_manager = ElyticsDataManager()
tag_manager = None


def build_layout():
    return dbc.Container(
        fluid=True,
        className="px-0 co-reporting-shell",
        style={
            "height": "calc(100vh - 110px)",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
        },
        children=[
            dcc.Store(id="store-series-refresh", storage_type="memory", data=0),
            html.Div(
                className="co-reporting-hero",
                children=[
                    html.Div(
                        className="elytics-brand-row",
                        children=[
                            html.Img(
                                src="/assets/elytics-logo.svg",
                                className="elytics-brand-logo",
                                alt="Elytics - CO2 Energy Stack Analytics & Optimization Platform",
                            ),
                            html.Div(
                                className="elytics-hero-copy",
                                children=[
                                    html.Div(
                                        "CO2 electrolyzers convert carbon dioxide into valuable chemicals and fuels using electricity, enabling carbon capture and utilization.",
                                        className="co-reporting-subtitle",
                                    ),
                                    html.Div(
                                        "Databricks-backed CO reporting with Redis-cached query results for fast experiment analysis.",
                                        className="co-reporting-supporting-copy",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            dcc.Tabs(
                id="main-tabs",
                value="tab-standard",
                className="co-reporting-tabs",
                parent_style={
                    "flex": "1 1 auto",
                    "display": "flex",
                    "flexDirection": "column",
                    "minHeight": "0",
                },
                content_style={
                    "flex": "1 1 auto",
                    "display": "flex",
                    "flexDirection": "column",
                    "minHeight": "0",
                    "overflow": "hidden",
                },
                children=[
                    dcc.Tab(
                        label="Standard Reports",
                        value="tab-standard",
                        children=standard_reports.layout(data_manager),
                    ),
                    dcc.Tab(
                        label="Custom Reports",
                        value="tab-custom",
                        children=custom_reports.layout(data_manager, tag_manager),
                    ),
                ],
            ),
        ],
    )


def register_callbacks(app):
    standard_reports.register_callbacks(app, data_manager)
    custom_reports.register_callbacks(app, data_manager, tag_manager)

