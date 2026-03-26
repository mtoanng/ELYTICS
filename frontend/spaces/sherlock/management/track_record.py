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
from typing import Optional, List

from services.backend_service import get_metadata


register_page(
    __name__,
    path="/sherlock/management/track-record",
    title="HOLMES - Sherlock - Track Record",
)


# Expected columns from split views.
META_COLS = [
    "sample_name",
    "sample_type",
    "sample_state",
    "sample_type_state",
    "run_hours",
    "number_of_cells",
    "leepa_number",
    "production_plant",
    "description",
    "cellunit_name",
    "ccm_name",
    "ptl_name",
    "gdl_name",
    "active_area_per_cell",
]

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


def _build_runtime_agg(df_meta: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_columns(df_meta, META_COLS)
    if df.empty:
        return pd.DataFrame(columns=META_COLS + ["total_run_hours"])

    df["sample_name"] = df["sample_name"].fillna("").astype(str).str.strip()
    df["run_hours"] = pd.to_numeric(df["run_hours"], errors="coerce").fillna(0.0)

    agg_map = {
        "sample_type": "first",
        "sample_state": "first",
        "sample_type_state": "first",
        "run_hours": "sum",
        "number_of_cells": "max",
        "leepa_number": "first",
        "production_plant": "first",
        "description": "first",
        "cellunit_name": "first",
        "ccm_name": "first",
        "ptl_name": "first",
        "gdl_name": "first",
        "active_area_per_cell": "first",
    }

    available_agg_map = {
        key: value for key, value in agg_map.items() if key in df.columns
    }
    df_runtime_agg = df.groupby("sample_name", as_index=False).agg(available_agg_map)
    df_runtime_agg["total_run_hours"] = df_runtime_agg["run_hours"]
    df_runtime_agg = df_runtime_agg.sort_values(
        ["total_run_hours", "sample_name"],
        ascending=[False, True],
    )
    return df_runtime_agg


def _build_kpi_grouped(df_runtime_agg: pd.DataFrame) -> pd.DataFrame:
    if df_runtime_agg.empty:
        return pd.DataFrame(
            columns=["sample_type_state", "number_of_cells", "run_hours"]
        )

    df_kpi = df_runtime_agg.copy()
    df_kpi = df_kpi[
        df_kpi["sample_type_state"].isin(["Gen 1 - Proto 1", "Gen 1 - Proto 2"])
    ]
    df_kpi = df_kpi[df_kpi["run_hours"] > 0]
    if df_kpi.empty:
        return pd.DataFrame(
            columns=["sample_type_state", "number_of_cells", "run_hours"]
        )

    df_kpi["number_of_cells"] = df_kpi["number_of_cells"].fillna("Unknown").astype(str)
    return df_kpi.groupby(["sample_type_state", "number_of_cells"], as_index=False)[
        "run_hours"
    ].sum()


def _build_runtime_figure(df_runtime_agg: pd.DataFrame) -> go.Figure:
    df = _ensure_columns(df_runtime_agg, META_COLS + ["total_run_hours"])
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    color_map = {
        name: palette[i % len(palette)]
        for i, name in enumerate(df["sample_name"].dropna().tolist())
    }
    marker_colors = [color_map.get(name, palette[0]) for name in df["sample_name"]]

    fig = go.Figure(
        go.Bar(
            x=df["sample_name"],
            y=df["total_run_hours"],
            marker_color=marker_colors,
            customdata=df[PLOT_HOVER_COLS],
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Total runtime: %{y:.0f} h<br><br>"
                "Type / State: %{customdata[0]} - %{customdata[1]}<br>"
                "Plant: %{customdata[2]}<br>"
                "CCM: %{customdata[3]}<br>"
                "PTL: %{customdata[4]}<br>"
                "GDL: %{customdata[5]}<br>"
                "Active area / cell: %{customdata[6]}<br>"
                "Leepa number: %{customdata[7]}"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title="Top Gen 1 Stacks by Total Operational Runtime",
        xaxis_title="Stack (Sample name)",
        yaxis_title="Operational runtime [h]",
        margin=dict(l=40, r=20, t=40, b=40),
    )
    fig.update_xaxes(categoryorder="array", categoryarray=df["sample_name"])
    return fig


def _build_kpi_figure(df_kpi_grouped: pd.DataFrame) -> go.Figure:
    df = _ensure_columns(
        df_kpi_grouped, ["sample_type_state", "number_of_cells", "run_hours"]
    )
    fig = go.Figure()

    if not df.empty:
        cell_values = sorted(
            df["number_of_cells"].fillna("Unknown").astype(str).unique()
        )
        for cell in cell_values:
            df_cell = df[df["number_of_cells"].astype(str) == cell]
            fig.add_trace(
                go.Bar(
                    x=df_cell["sample_type_state"],
                    y=df_cell["run_hours"],
                    name=str(cell),
                )
            )

    fig.update_layout(
        title="Run Hours per Sample Type grouped by Number of Cells",
        xaxis_title="Sample Type",
        yaxis_title="Run Hours",
        barmode="stack",
        legend_title_text="Number of Cells",
        margin=dict(l=40, r=20, t=40, b=40),
    )
    return fig


def _prepare_meta_payload(meta_rows: Optional[List[dict]]):
    df_meta = pd.DataFrame(meta_rows or [])
    df_runtime_agg = _build_runtime_agg(df_meta)
    df_kpi_grouped = _build_kpi_grouped(df_runtime_agg)
    return df_runtime_agg, df_kpi_grouped


USAGE_BLOCKQUOTE_TEXT = [
    "The top bar charts show total operational runtime per Gen 1 stack and sample types.",
    "Hover on a bar to see detailed stack information.",
    "The left chart aggregates run hours by sample type and number of cells.",
]

fig_runtime = _build_runtime_figure(
    pd.DataFrame(columns=META_COLS + ["total_run_hours"])
)
fig_kpi = _build_kpi_figure(
    pd.DataFrame(columns=["sample_type_state", "number_of_cells", "run_hours"])
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
                                "Top performing Gen 1 stacks based on total operational runtime (based on cloud data)",
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
                                        cols=2,
                                        spacing="md",
                                        children=[
                                            dcc.Graph(
                                                id="runtime-kpi",
                                                figure=fig_kpi,
                                                config={"responsive": True},
                                                style={
                                                    "width": "100%",
                                                    "height": "420px",
                                                },
                                            ),
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
    Output("runtime-kpi", "figure"),
    Output("runtime-bar", "figure"),
    Input("track-meta-data", "data"),
    Input("theme-store", "data"),
)
def update_top_charts(meta_rows, theme):

    df_runtime_agg, df_kpi_grouped = _prepare_meta_payload(meta_rows)
    runtime_fig = apply_theme(_build_runtime_figure(df_runtime_agg), theme)
    kpi_fig = apply_theme(_build_kpi_figure(df_kpi_grouped), theme)
    return kpi_fig, runtime_fig
