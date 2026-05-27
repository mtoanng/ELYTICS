from dash import (
    dcc,
    callback,
    Output,
    Input,
    State,
    no_update,
    clientside_callback,
)
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import plotly.graph_objects as go
import pandas as pd
from typing import List

from services.backend_service import get_metadata, get_tabular

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

USAGE_BLOCKQUOTE_TEXT = [
    "The top chart shows total runtime for GEN 1 Proto 1 stacks.",
    "Each bar corresponds to one sample.",
    "Hover on a bar to inspect runtime and stack metadata.",
    "Select a sample name from the filter or by clicking on the plot bars to load detailed data shown below.",
    "Use the x-axis toggle to switch the lower charts between runtime hours and date when a time column is available.",
    "NOTE: Current in-depth plots show the full timeseries (1hr) data. The conditioning events are not yet available in the data sources.",
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


def apply_theme(fig, theme):
    template = "plotly_dark" if theme == "dark" else "plotly"
    fig.update_layout(template=template)
    return fig


ORDER_ID_PALETTE = [
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


def get_order_id_color(order_id, order_ids_list):
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
    uirevision: str,
    margin_bottom: int = 0,
    yaxis_range: list | None = None,
    y_multiplier: float = 1.0,
) -> go.Figure:
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
        unique_order_ids = sorted(plot_df["order_id"].dropna().unique())

        x_hover = "%{x|%Y-%m-%d %H:%M}" if x_axis_mode == "time" else "%{x:.0f} h"
        scatter_mode = "markers" if x_axis_mode == "time" else "lines+markers"

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

    is_dark = theme == "dark"

    layout_dict = dict(
        xaxis_title=x_title,
        yaxis_title=yaxis_title,
        margin=dict(l=40, r=20, t=12, b=margin_bottom),
        showlegend=True,
        uirevision=uirevision,
        legend=dict(
            x=0.98,
            y=0.98,
            xanchor="right",
            yanchor="top",
            bgcolor="rgba(20, 24, 28, 0.85)" if is_dark else "rgba(255, 255, 255, 0.9)",
            bordercolor=(
                "rgba(255, 255, 255, 0.20)" if is_dark else "rgba(0, 0, 0, 0.15)"
            ),
            borderwidth=1,
            font=dict(color="#f1f3f5" if is_dark else "#1f2937"),
        ),
    )
    if yaxis_range is not None:
        layout_dict["yaxis"] = dict(range=yaxis_range)
    fig.update_layout(**layout_dict)
    return apply_theme(fig, theme)


def create_track_record_page(ns: str):
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

    layout = dmc.Container(
        size="xl",
        py="md",
        children=[
            dmc.Stack(
                gap="md",
                children=[
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
                                        id=f"{ns}-trackrecord-usage-toggle",
                                        variant="subtle",
                                        color="blue",
                                        size="md",
                                        radius="xl",
                                    ),
                                ],
                            ),
                            dmc.Text(
                                "Total runtime for GEN 1 Proto 1 stacks by sample name (based on cloud data).",
                                c="dimmed",
                            ),
                            dmc.Collapse(
                                id=f"{ns}-trackrecord-usage-collapse",
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
                    dcc.Store(id=f"{ns}-trackrecord-usage-open", data=False),
                    dcc.Store(id=f"{ns}-trackrecord-detail-data", data=[]),
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
                                                id=f"{ns}-runtime-bar",
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
                                                    id=f"{ns}-trackrecord-sample-filter",
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
                                                        dmc.Text(
                                                            "X axis", size="sm", fw=500
                                                        ),
                                                        dmc.SegmentedControl(
                                                            id=f"{ns}-trackrecord-x-axis-mode",
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
                                                        id=f"{ns}-trackrecord-uCell-plot",
                                                        figure=fig_uCell,
                                                        config={"responsive": True},
                                                        style={
                                                            "width": "100%",
                                                            "height": "280px",
                                                        },
                                                    ),
                                                    dcc.Graph(
                                                        id=f"{ns}-trackrecord-concO2H2-plot",
                                                        figure=fig_concO2H2,
                                                        config={"responsive": True},
                                                        style={
                                                            "width": "100%",
                                                            "height": "280px",
                                                        },
                                                    ),
                                                    dcc.Graph(
                                                        id=f"{ns}-trackrecord-concH2O2-plot",
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
                    dcc.Store(id=f"{ns}-track-meta-data", data=[]),
                ],
            ),
        ],
    )

    @callback(
        Output(f"{ns}-track-meta-data", "data"),
        Input(f"{ns}-runtime-bar", "id"),
    )
    def load_track_record_meta(_):
        try:
            return get_metadata("sherlock", "track_record")
        except Exception:
            return []

    @callback(
        Output(f"{ns}-trackrecord-usage-open", "data"),
        Input(f"{ns}-trackrecord-usage-toggle", "n_clicks"),
        State(f"{ns}-trackrecord-usage-open", "data"),
        prevent_initial_call=True,
    )
    def toggle_usage_blockquote(n_clicks, is_open):
        if n_clicks is None:
            return no_update
        return not bool(is_open)

    @callback(
        Output(f"{ns}-trackrecord-usage-collapse", "opened"),
        Input(f"{ns}-trackrecord-usage-open", "data"),
    )
    def sync_usage_blockquote(is_open):
        return bool(is_open)

    @callback(
        Output(f"{ns}-trackrecord-sample-filter", "data"),
        Output(f"{ns}-trackrecord-sample-filter", "value"),
        Input(f"{ns}-track-meta-data", "data"),
        Input(f"{ns}-runtime-bar", "clickData"),
        Input(f"{ns}-runtime-bar", "selectedData"),
        State(f"{ns}-trackrecord-sample-filter", "value"),
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
        Output(f"{ns}-runtime-bar", "figure"),
        Input(f"{ns}-track-meta-data", "data"),
        Input("theme-store", "data"),
    )
    def update_top_charts(meta_rows, theme):
        df = pd.DataFrame(meta_rows or [])
        df = _ensure_columns(df, PLOT_COLS + PLOT_HOVER_COLS)

        df["sample_name"] = df["sample_name"].fillna("Unknown").astype(str)
        df["run_hours"] = pd.to_numeric(df["run_hours"], errors="coerce").fillna(0.0)
        df = df.sort_values(["run_hours", "sample_name"], ascending=[False, True])

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
        Output(f"{ns}-trackrecord-detail-data", "data"),
        Input(f"{ns}-trackrecord-sample-filter", "value"),
    )
    def load_detail_data(sample_name):
        if not sample_name:
            return []

        try:
            df = get_tabular(
                "sherlock",
                "track_record",
                filters={"sample_name": sample_name},
                sort_by="hours_run",
                sort_dir="asc",
            )
        except Exception:
            return []

        df = _ensure_columns(df, DETAIL_COLS)
        return df.to_dict("records")

    @callback(
        Output(f"{ns}-trackrecord-uCell-plot", "figure"),
        Output(f"{ns}-trackrecord-concO2H2-plot", "figure"),
        Output(f"{ns}-trackrecord-concH2O2-plot", "figure"),
        Input(f"{ns}-trackrecord-detail-data", "data"),
        Input(f"{ns}-trackrecord-sample-filter", "value"),
        Input(f"{ns}-trackrecord-x-axis-mode", "value"),
        Input("theme-store", "data"),
    )
    def update_detail_plots(detail_rows, sample_name, x_axis_mode, theme):
        df = _ensure_columns(pd.DataFrame(detail_rows or []), DETAIL_COLS)
        uirevision = f"{ns}-trackrecord-{sample_name or 'none'}-{x_axis_mode}"

        ucell_fig = build_detail_plot(
            df=df,
            value_col="uCell",
            yaxis_title="uCell",
            hover_label="uCell",
            x_axis_mode=x_axis_mode,
            theme=theme,
            uirevision=uirevision,
            margin_bottom=0,
        )
        conco2h2_fig = build_detail_plot(
            df=df,
            value_col="concO2H2",
            yaxis_title="concO2H2 [ppm]",
            hover_label="concO2H2",
            x_axis_mode=x_axis_mode,
            theme=theme,
            uirevision=uirevision,
            margin_bottom=0,
        )
        conch2o2_fig = build_detail_plot(
            df=df,
            value_col="concH2O2",
            yaxis_title="concH2O2 [%]",
            hover_label="concH2O2",
            x_axis_mode=x_axis_mode,
            theme=theme,
            uirevision=uirevision,
            margin_bottom=20,
        )
        return ucell_fig, conco2h2_fig, conch2o2_fig

    clientside_callback(
        f"""
        function(uRelayout, oRelayout, hRelayout, uFigure, oFigure, hFigure) {{
            const triggered = window.dash_clientside.callback_context.triggered;
            if (!triggered || !triggered.length) {{
                return [
                    window.dash_clientside.no_update,
                    window.dash_clientside.no_update,
                    window.dash_clientside.no_update
                ];
            }}

            const propId = triggered[0].prop_id || "";
            if (propId.indexOf("relayoutData") === -1) {{
                return [
                    window.dash_clientside.no_update,
                    window.dash_clientside.no_update,
                    window.dash_clientside.no_update
                ];
            }}

            const relayout = triggered[0].value || {{}};
            let xRange = null;
            let resetAutorange = false;

            if (Array.isArray(relayout["xaxis.range"]) && relayout["xaxis.range"].length === 2) {{
                xRange = relayout["xaxis.range"];
            }} else if (relayout["xaxis.range[0]"] !== undefined && relayout["xaxis.range[1]"] !== undefined) {{
                xRange = [relayout["xaxis.range[0]"], relayout["xaxis.range[1]"]];
            }} else if (relayout["xaxis.autorange"] === true) {{
                resetAutorange = true;
            }}

            if (!xRange && !resetAutorange) {{
                return [
                    window.dash_clientside.no_update,
                    window.dash_clientside.no_update,
                    window.dash_clientside.no_update
                ];
            }}

            function syncFigure(fig) {{
                if (!fig) {{
                    return window.dash_clientside.no_update;
                }}

                const nextFig = JSON.parse(JSON.stringify(fig));
                nextFig.layout = nextFig.layout || {{}};
                nextFig.layout.xaxis = nextFig.layout.xaxis || {{}};

                if (xRange) {{
                    nextFig.layout.xaxis.range = xRange;
                    nextFig.layout.xaxis.autorange = false;
                }} else {{
                    delete nextFig.layout.xaxis.range;
                    nextFig.layout.xaxis.autorange = true;
                }}

                return nextFig;
            }}

            return [syncFigure(uFigure), syncFigure(oFigure), syncFigure(hFigure)];
        }}
        """,
        Output(f"{ns}-trackrecord-uCell-plot", "figure", allow_duplicate=True),
        Output(f"{ns}-trackrecord-concO2H2-plot", "figure", allow_duplicate=True),
        Output(f"{ns}-trackrecord-concH2O2-plot", "figure", allow_duplicate=True),
        Input(f"{ns}-trackrecord-uCell-plot", "relayoutData"),
        Input(f"{ns}-trackrecord-concO2H2-plot", "relayoutData"),
        Input(f"{ns}-trackrecord-concH2O2-plot", "relayoutData"),
        State(f"{ns}-trackrecord-uCell-plot", "figure"),
        State(f"{ns}-trackrecord-concO2H2-plot", "figure"),
        State(f"{ns}-trackrecord-concH2O2-plot", "figure"),
        prevent_initial_call=True,
    )

    return layout
