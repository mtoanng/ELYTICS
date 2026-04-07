from dash import (
    dcc,
    callback,
    Output,
    Input,
    State,
    register_page,
    no_update,
)
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import plotly.graph_objects as go
import pandas as pd
from typing import List

from services.backend_service import get_metadata


register_page(
    __name__,
    path="/sherlock/management/track-record",
    title="HOLMES - Sherlock - Track Record",
)

PLOT_COLS = ["sample_name", "run_hours"]

PLOT_HOVER_COLS = [
    "sample_type",
    "sample_state",
    "production_plant",
    "ccm_name",
    "ptl_name",
    "gdl_name",
    "active_area_per_cell",
    "leepa_number",
]

def _ensure_columns(df: pd.DataFrame, required_cols: List[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=required_cols)
    out = df.copy()
    for col in required_cols:
        if col not in out.columns:
            out[col] = None
    return out


USAGE_BLOCKQUOTE_TEXT = [
    "The chart shows run hours directly from column run_hours.",
    "Each bar corresponds to one sample_name.",
    "Hover on a bar to inspect runtime and stack metadata.",
]

fig_runtime = go.Figure(
    go.Bar(x=[], y=[], marker_color="#1f77b4")
)
fig_runtime.update_layout(
    title="Run Hours per Sample Name",
    xaxis_title="Sample Name",
    yaxis_title="Run Hours [h]",
    margin=dict(l=40, r=20, t=40, b=40),
)


def track_record_layout():
    return dmc.Container(
        size="xl",
        py="md",
        children=[
            dmc.Stack(
                gap="md",
                children=[
                    # Header + usage help
                    dmc.Stack(
                        gap=2,
                        children=[
                            dmc.Group(
                                gap="xs",
                                align="center",
                                children=[
                                    dmc.Title("Track Record", order=2),
                                    dmc.ActionIcon(
                                        DashIconify(
                                            icon="material-symbols:info-outline",
                                            width=20,
                                        ),
                                        id="trackrecord-usage-toggle",
                                        variant="subtle",
                                        color="blue",
                                        size="md",
                                        radius="xl",
                                    ),
                                ],
                            ),
                            dmc.Text(
                                "Run hours by sample name (based on cloud data)",
                                c="dimmed",
                            ),
                            # Use in_ instead of opened for dmc.Collapse v2.6.0
                            dmc.Collapse(
                                id="trackrecord-usage-collapse",
                                opened=False,
                                children=dmc.Blockquote(
                                    dmc.List(
                                        withPadding=False,
                                        children=[
                                            dmc.ListItem(item)
                                            for item in USAGE_BLOCKQUOTE_TEXT
                                        ],
                                    ),
                                    color="blue",
                                ),
                            ),
                        ],
                    ),
                    dcc.Store(id="trackrecord-usage-open", data=False),
                    dmc.Stack(
                        gap="md",
                        style={"width": "100%"},
                        children=[
                            dmc.Paper(
                                withBorder=True,
                                p="md",
                                radius="md",
                                children=[
                                    dmc.SimpleGrid(
                                        cols=1,
                                        spacing="md",
                                        children=[
                                            dcc.Graph(
                                                id="runtime-bar",
                                                figure=fig_runtime,
                                                config={"responsive": True},
                                                style={
                                                    "width": "100%",
                                                    "height": "420px",
                                                },
                                            ),
                                        ],
                                    )
                                ],
                            ),
                        ],
                    ),
                    dcc.Store(id="track-meta-data", data=[]),
                ],
            ),
        ],
    )


# If your framework expects a callable layout, this is fine.
# If you need a component, use: layout = track_record_layout()
layout = track_record_layout


@callback(
    Output("track-meta-data", "data"),
    Input("runtime-bar", "id"),
)
def load_track_record_meta(_):
    try:
        return get_metadata("sherlock", "track_record")
    except Exception:
        return []


# =====================================================
# CALLBACK: TOGGLE HELP INFO
# =====================================================
@callback(
    Output("trackrecord-usage-open", "data"),
    Input("trackrecord-usage-toggle", "n_clicks"),
    State("trackrecord-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage_blockquote(n_clicks, is_open):
    if n_clicks is None:
        return no_update
    return not bool(is_open)


@callback(
    Output("trackrecord-usage-collapse", "opened"),
    Input("trackrecord-usage-open", "data"),
)
def sync_usage_blockquote(is_open):
    return bool(is_open)


def apply_theme(fig, theme):
    template = "plotly_dark" if theme == "dark" else "plotly"
    fig.update_layout(template=template)
    return fig


@callback(
    Output("runtime-bar", "figure"),
    Input("track-meta-data", "data"),
    Input("theme-store", "data"),
)
def update_top_charts(meta_rows, theme):
    df = pd.DataFrame(meta_rows or [])
    df = _ensure_columns(df, PLOT_COLS + PLOT_HOVER_COLS)

    df["sample_name"] = df["sample_name"].fillna("Unknown").astype(str)
    df["run_hours"] = pd.to_numeric(df["run_hours"], errors="coerce").fillna(0.0)
    df = df.sort_values(["run_hours", "sample_name"], ascending=[False, True])

    # Keep hover values readable and avoid NaN in tooltip.
    hover_df = df[PLOT_HOVER_COLS].fillna("N/A").astype(str)

    palette = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]
    marker_colors = [palette[i % len(palette)] for i in range(len(df))]

    runtime_fig = go.Figure(
        go.Bar(
            x=df["sample_name"],
            y=df["run_hours"],
            customdata=hover_df,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Run hours: %{y:.0f} h<br><br>"
                "Sample type: %{customdata[0]}<br>"
                "Sample state: %{customdata[1]}<br>"
                "Plant: %{customdata[2]}<br>"
                "CCM: %{customdata[3]}<br>"
                "PTL: %{customdata[4]}<br>"
                "GDL: %{customdata[5]}<br>"
                "Active area / cell: %{customdata[6]}<br>"
                "Leepa number: %{customdata[7]}"
                "<extra></extra>"
            ),
            marker_color=marker_colors,
        )
    )
    runtime_fig.update_layout(
        title="Run Hours per Sample Name",
        xaxis_title="Sample Name",
        yaxis_title="Run Hours [h]",
        margin=dict(l=40, r=20, t=40, b=40),
    )
    runtime_fig.update_xaxes(categoryorder="array", categoryarray=df["sample_name"])
    runtime_fig = apply_theme(runtime_fig, theme)
    return runtime_fig
