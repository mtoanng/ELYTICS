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

from services.backend_service import get_metadata, get_tabular


register_page(
    __name__,
    path="/sherlock/management/track-record",
    title="HOLMES - Sherlock - Track Record",
)

PLOT_COLS = ["sample_name", "run_hours"]
DETAIL_COLS = ["order_id", "hours_run", "time", "date", "uCell", "concO2H2", "concH2O2"]
X_AXIS_OPTIONS = [
    {"label": "Hours run", "value": "hours_run"},
    {"label": "Date", "value": "time"},
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


def _sample_from_bar_interaction(click_data, selected_data):
    if isinstance(selected_data, dict):
        points = selected_data.get("points") or []
        if points:
            sample_name = points[0].get("x")
            if sample_name:
                return str(sample_name)

    if isinstance(click_data, dict):
        points = click_data.get("points") or []
        if points:
            sample_name = points[0].get("x")
            if sample_name:
                return str(sample_name)

    return None


def _default_sample_from_rank(meta_rows) -> str | None:
    meta_df = pd.DataFrame(meta_rows or [])
    if not meta_df.empty and {"sample_name", "rn"}.issubset(meta_df.columns):
        meta_df = meta_df.copy()
        meta_df["sample_name"] = meta_df["sample_name"].astype(str).str.strip()
        meta_df["rn"] = pd.to_numeric(meta_df["rn"], errors="coerce")
        meta_df = meta_df.dropna(subset=["sample_name", "rn"])
        meta_df = meta_df[meta_df["sample_name"] != ""]
        if not meta_df.empty:
            meta_df = meta_df.sort_values(["rn", "sample_name"], ascending=[True, True])
            return str(meta_df.iloc[0]["sample_name"])

    try:
        rank_df = get_tabular(
            "sherlock",
            "track_record",
            sort_by="rn",
            sort_dir="asc",
        )
    except Exception:
        return None

    rank_df = _ensure_columns(rank_df, ["sample_name", "rn"])
    rank_df["sample_name"] = rank_df["sample_name"].astype(str).str.strip()
    rank_df["rn"] = pd.to_numeric(rank_df["rn"], errors="coerce")
    rank_df = rank_df.dropna(subset=["sample_name", "rn"])
    rank_df = rank_df[rank_df["sample_name"] != ""]
    if rank_df.empty:
        return None

    rank_df = rank_df.sort_values(["rn", "sample_name"], ascending=[True, True])
    return str(rank_df.iloc[0]["sample_name"])


USAGE_BLOCKQUOTE_TEXT = [
    "The top chart shows total runtime for GEN 1 Proto 1 stacks from column run_hours.",
    "Each bar corresponds to one sample_name.",
    "Hover on a bar to inspect runtime and stack metadata.",
    "Select a sample name below to load detailed uCell, concO2H2, and concH2O2 data from track_record tabular data.",
    "Use the x-axis toggle to switch the lower charts between runtime hours and date when a time column is available.",
]

fig_runtime = go.Figure(go.Bar(x=[], y=[], marker_color="#1f77b4"))
fig_runtime.update_layout(
    title="Total Runtime per Sample Name for GEN 1 Proto 1 stacks",
    xaxis_title="Sample Name",
    yaxis_title="Total Runtime [h]",
    clickmode="event+select",
    margin=dict(l=40, r=20, t=40, b=40),
)

fig_uCell = go.Figure()
fig_uCell.update_layout(
    title="uCell",
    xaxis_title="Hours run [hr]",
    yaxis_title="uCell",
)

fig_concO2H2 = go.Figure()
fig_concO2H2.update_layout(
    title="concO2H2",
    xaxis_title="Hours run [hr]",
    yaxis_title="concO2H2 [%]",
)

fig_concH2O2 = go.Figure()
fig_concH2O2.update_layout(
    title="concH2O2",
    xaxis_title="Hours run [hr]",
    yaxis_title="concH2O2 [%]",
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
                                "Total runtime for GEN 1 Proto 1 stacks by sample name (based on cloud data)",
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
                            dmc.Paper(
                                withBorder=True,
                                p="md",
                                radius="md",
                                children=dmc.Stack(
                                    gap="xs",
                                    children=[
                                        dmc.Group(
                                            align="end",
                                            children=[
                                                dmc.Select(
                                                    id="trackrecord-sample-filter",
                                                    label="Sample name",
                                                    placeholder="Select a sample name",
                                                    searchable=True,
                                                    clearable=True,
                                                    data=[],
                                                    nothingFoundMessage="No sample names",
                                                    style={"flex": 1},
                                                ),
                                                dmc.Stack(
                                                    gap=4,
                                                    style={"width": "220px"},
                                                    children=[
                                                        dmc.Text("X axis", size="sm", fw=500),
                                                        dmc.SegmentedControl(
                                                            id="trackrecord-x-axis-mode",
                                                            data=X_AXIS_OPTIONS,
                                                            value="hours_run",
                                                            size="xs",
                                                        ),
                                                    ],
                                                ),
                                            ],
                                        ),
                                        dcc.Loading(
                                            type="circle",
                                            delay_show=150,
                                            children=dmc.Stack(
                                                gap="0",
                                                children=[
                                                    dcc.Graph(
                                                        id="trackrecord-uCell-plot",
                                                        figure=fig_uCell,
                                                        config={"responsive": True},
                                                        style={
                                                            "width": "100%",
                                                            "height": "280px",
                                                        },
                                                    ),
                                                    dcc.Graph(
                                                        id="trackrecord-concO2H2-plot",
                                                        figure=fig_concO2H2,
                                                        config={"responsive": True},
                                                        style={
                                                            "width": "100%",
                                                            "height": "280px",
                                                        },
                                                    ),
                                                    dcc.Graph(
                                                        id="trackrecord-concH2O2-plot",
                                                        figure=fig_concH2O2,
                                                        config={"responsive": True},
                                                        style={
                                                            "width": "100%",
                                                            "height": "280px",
                                                        },
                                                    ),
                                                ],
                                            ),
                                        ),
                                    ],
                                ),
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


# Color palette for order_ids
ORDER_ID_PALETTE = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # gray
    "#bcbd22",  # olive
    "#17becf",  # cyan
]


def get_order_id_color(order_id, order_ids_list):
    """Get a consistent color for an order_id based on its index in the sorted list."""
    try:
        idx = sorted(set(order_ids_list)).index(order_id)
        return ORDER_ID_PALETTE[idx % len(ORDER_ID_PALETTE)]
    except (ValueError, IndexError):
        return ORDER_ID_PALETTE[0]


def build_detail_plot(
    df: pd.DataFrame,
    value_col: str,
    yaxis_title: str,
    hover_label: str,
    x_axis_mode: str,
    theme: str,
    margin_bottom: int = 0,
    yaxis_range: list | None = None,
    y_multiplier: float = 1.0,
) -> go.Figure:
    """Build a detail plot with multiple traces, one per order_id, each with its own color."""
    plot_df = df.copy()
    plot_df[value_col] = pd.to_numeric(plot_df[value_col], errors="coerce")
    if y_multiplier != 1.0:
        plot_df[value_col] = plot_df[value_col] * y_multiplier
    plot_df["order_id"] = plot_df["order_id"].fillna("Unknown").astype(str).str.strip()

    if x_axis_mode == "time":
        x_col = "time"
        x_title = "Date"
        if x_col not in plot_df.columns:
            plot_df = pd.DataFrame(columns=[value_col])
        else:
            plot_df[x_col] = pd.to_datetime(plot_df[x_col], errors="coerce")
            plot_df = plot_df.dropna(subset=[x_col, value_col]).sort_values(x_col)
    else:
        x_col = "hours_run"
        x_title = "Hours run [hr]"
        plot_df[x_col] = pd.to_numeric(plot_df[x_col], errors="coerce")
        plot_df = plot_df.dropna(subset=[x_col, value_col]).sort_values(x_col)

    fig = go.Figure()
    
    if not plot_df.empty and "order_id" in plot_df.columns:
        # Get unique order_ids in sorted order for consistent coloring
        unique_order_ids = sorted(plot_df["order_id"].dropna().unique())
        
        x_hover = "%{x|%Y-%m-%d %H:%M}" if x_axis_mode == "time" else "%{x:.0f} h"
        scatter_mode = "markers" if x_axis_mode == "time" else "lines+markers"
        
        # Create one trace per order_id
        for order_id in unique_order_ids:
            order_df = plot_df[plot_df["order_id"] == order_id].copy()
            if not order_df.empty:
                color = get_order_id_color(order_id, unique_order_ids)
                fig.add_trace(
                    go.Scatter(
                        x=order_df[x_col],
                        y=order_df[value_col],
                        mode=scatter_mode,
                        name=order_id,
                        marker=dict(size=8, color=color),
                        line=dict(width=2, color=color),
                        hovertemplate=(
                            f"Order ID: {order_id}<br>{x_title}: {x_hover}<br>{hover_label}: %{{y:.3f}}<extra></extra>"
                        ),
                    )
                )
    elif x_axis_mode == "time" and plot_df.empty:
        fig.add_annotation(
            text="No time column available for this dataset",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )

    layout_dict = dict(
        xaxis_title=x_title,
        yaxis_title=yaxis_title,
        margin=dict(l=40, r=20, t=12, b=margin_bottom),
        showlegend=True,
        legend=dict(x=0.98, y=0.98, xanchor="right", yanchor="top", bgcolor="rgba(255, 255, 255, 0.9)"),
    )
    if yaxis_range is not None:
        layout_dict["yaxis"] = dict(range=yaxis_range)
    fig.update_layout(**layout_dict)
    return apply_theme(fig, theme)


@callback(
    Output("trackrecord-sample-filter", "data"),
    Output("trackrecord-sample-filter", "value"),
    Input("track-meta-data", "data"),
    Input("runtime-bar", "clickData"),
    Input("runtime-bar", "selectedData"),
    State("trackrecord-sample-filter", "value"),
)
def populate_sample_filter(meta_rows, click_data, selected_data, current_value):
    df = pd.DataFrame(meta_rows or [])
    df = _ensure_columns(df, ["sample_name"])

    sample_names = sorted(
        name
        for name in df["sample_name"].dropna().astype(str).str.strip().unique()
        if name
    )
    options = [{"label": name, "value": name} for name in sample_names]

    selected_from_chart = _sample_from_bar_interaction(click_data, selected_data)
    if selected_from_chart in sample_names:
        return options, selected_from_chart

    if current_value in sample_names:
        return options, current_value

    default_sample = _default_sample_from_rank(meta_rows)
    if default_sample in sample_names:
        return options, default_sample

    if sample_names:
        return options, sample_names[0]
    return [], None


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
                "Total runtime: %{y:.0f} h<br><br>"
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
        title="Total Runtime per Sample Name",
        xaxis_title="Sample Name",
        yaxis_title="Total Runtime [h]",
        margin=dict(l=40, r=20, t=40, b=40),
    )
    runtime_fig.update_xaxes(categoryorder="array", categoryarray=df["sample_name"])
    runtime_fig = apply_theme(runtime_fig, theme)
    return runtime_fig


@callback(
    Output("trackrecord-uCell-plot", "figure"),
    Output("trackrecord-concO2H2-plot", "figure"),
    Output("trackrecord-concH2O2-plot", "figure"),
    Input("trackrecord-sample-filter", "value"),
    Input("trackrecord-x-axis-mode", "value"),
    Input("theme-store", "data"),
)
def update_detail_plots(sample_name, x_axis_mode, theme):
    if not sample_name:
        df = pd.DataFrame(columns=DETAIL_COLS)
    else:
        try:
            df = get_tabular(
                "sherlock",
                "track_record",
                filters={"sample_name": sample_name},
                sort_by="hours_run",
                sort_dir="asc",
            )
        except Exception:
            df = pd.DataFrame(columns=DETAIL_COLS)

    df = _ensure_columns(df, DETAIL_COLS)

    uCell_fig = build_detail_plot(
        df=df,
        value_col="uCell",
        yaxis_title="uCell",
        hover_label="uCell",
        x_axis_mode=x_axis_mode,
        theme=theme,
        margin_bottom=0,
    )
    concO2H2_fig = build_detail_plot(
        df=df,
        value_col="concO2H2",
        yaxis_title="concO2H2 [ppm]",
        hover_label="concO2H2",
        x_axis_mode=x_axis_mode,
        theme=theme,
        margin_bottom=0,
        yaxis_range=[0, 1],
    )
    concH2O2_fig = build_detail_plot(
        df=df,
        value_col="concH2O2",
        yaxis_title="concH2O2 [%]",
        hover_label="concH2O2",
        x_axis_mode=x_axis_mode,
        theme=theme,
        margin_bottom=20,
        yaxis_range=[0, 1],
    )
    return uCell_fig, concO2H2_fig, concH2O2_fig
