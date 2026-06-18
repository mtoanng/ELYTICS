from dash import (
    dcc,
    callback,
    callback_context,
    Output,
    Input,
    State,
    no_update,
)
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from typing import Callable, List

from config.signals import (
    get_signal_label,
    get_signal_title,
    get_signal_unit,
)
from services.backend_service import get_metadata, get_tabular

FILTER_WRAPPER_STYLE = {"flex": "1 1 0", "minWidth": "220px"}
FILTER_DROPDOWN_STYLE = {"width": "100%"}
LIMIT_INPUT_STYLES = {"input": {"height": "34px", "minHeight": "34px"}}

PLOT_COLS = ["sample_name", "run_hours"]
DETAIL_COLS = [
    "sample_name",
    "order_id",
    "time",
    "u_cell_avg",
    "c_h2_ino2",
    "c_o2_inh2",
    "u",
    "j",
    "p_cat_out",
    "t_an_in",
    "time_test",
    "time_run",
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
    "The top chart shows total runtime for GEN 1 Proto 1 stacks from column run_hours.",
    "Each bar corresponds to one sample_name.",
    "Hover on a bar to inspect runtime and stack metadata.",
    "Select a sample name from the filter or by clicking on the plot bars to load detailed data shown below.",
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


def _coerce_axis_range(lower, upper) -> list[float] | None:
    if lower in (None, "") or upper in (None, ""):
        return None

    try:
        lower_value = float(lower)
        upper_value = float(upper)
    except (TypeError, ValueError):
        return None

    if lower_value >= upper_value:
        return None

    return [lower_value, upper_value]


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

# Target line functions based on hypothetical degradation trends. These can be adjusted based on real data insights.
def _ucell_target_line(hours_run: pd.Series) -> np.ndarray:
    return 1.835 + 4e-3 * np.log(hours_run) + 2.9e-6 * hours_run

def _h2_in_o2_target_line(hours_run: pd.Series) -> np.ndarray:
    return 0.5+hours_run*((0.8 - 0.5) / (80000 - 0))


def _o2_in_h2_target_line(hours_run: pd.Series) -> np.ndarray:
    return 30+hours_run*((200 - 30) / (80000 - 0))

def get_order_id_color(order_id, order_ids_list):
    try:
        idx = sorted(set(order_ids_list)).index(order_id)
        return ORDER_ID_PALETTE[idx % len(ORDER_ID_PALETTE)]
    except (ValueError, IndexError):
        return ORDER_ID_PALETTE[0]


def _build_analysis_time_run(
    df: pd.DataFrame,
    selected_order_ids: list[str] | None,
) -> pd.DataFrame:
    plot_df = df.copy()
    plot_df["order_id"] = plot_df["order_id"].fillna("Unknown").astype(str).str.strip()
    plot_df["time"] = pd.to_datetime(plot_df["time"], errors="coerce")
    plot_df["time_run"] = pd.to_numeric(plot_df["time_run"], errors="coerce")

    selected = [str(order_id) for order_id in (selected_order_ids or []) if str(order_id).strip()]
    if selected:
        plot_df = plot_df[plot_df["order_id"].isin(selected)]

    plot_df = plot_df.dropna(subset=["time_run"])
    if plot_df.empty:
        plot_df["analysis_time_run"] = pd.Series(dtype=float)
        return plot_df

    if not selected:
        selected = plot_df["order_id"].dropna().astype(str).unique().tolist()

    if len(selected) <= 1:
        plot_df["analysis_time_run"] = plot_df["time_run"]
        return plot_df.sort_values(["time_run", "time", "order_id"], na_position="last")

    order_stats = (
        plot_df.groupby("order_id", dropna=False)
        .agg(
            min_time=("time", "min"),
            max_time_run=("time_run", "max"),
        )
        .reset_index()
    )
    order_stats["sort_min_time"] = order_stats["min_time"].fillna(pd.Timestamp.max)
    order_stats = order_stats.sort_values(["sort_min_time", "order_id"])

    offsets: dict[str, float] = {}
    cumulative_offset = 0.0
    for row in order_stats.itertuples(index=False):
        offsets[str(row.order_id)] = cumulative_offset
        if pd.notna(row.max_time_run):
            cumulative_offset += float(row.max_time_run)

    plot_df["analysis_time_run"] = plot_df["order_id"].map(offsets).fillna(0.0) + plot_df["time_run"]
    return plot_df.sort_values(["analysis_time_run", "time", "order_id"], na_position="last")


def _build_no_data_figure(
    title: str,
    yaxis_title: str,
    theme: str,
    uirevision: str,
    margin_bottom: int = 0,
    message: str = "No data available",
    x_range: list | None = None,
) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        xaxis_title="Hours run [h]",
        yaxis_title=yaxis_title,
        margin=dict(l=40, r=20, t=32, b=margin_bottom),
        showlegend=False,
        uirevision=uirevision,
        annotations=[
            dict(
                text=message,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=14),
            )
        ],
    )
    if x_range:
        fig.update_xaxes(range=x_range)
    return apply_theme(fig, theme)


def build_detail_plot(
    df: pd.DataFrame,
    title: str,
    value_col: str,
    yaxis_title: str,
    hover_label: str,
    theme: str,
    uirevision: str,
    selected_order_ids: list[str] | None = None,
    margin_bottom: int = 0,
    yaxis_range: list | None = None,
    y_multiplier: float = 1.0,
    target_line_function: Callable[[pd.Series], np.ndarray] | None = None,
    target_line_name: str | None = None,
    x_range: list | None = None,
    reset_autorange: bool = False,
) -> go.Figure:
    full_plot_df = df.copy()
    full_plot_df[value_col] = pd.to_numeric(full_plot_df[value_col], errors="coerce")
    if y_multiplier != 1.0:
        full_plot_df[value_col] = full_plot_df[value_col] * y_multiplier
    full_plot_df = _build_analysis_time_run(full_plot_df, selected_order_ids)

    default_x_range = None
    full_sorted_time_run = full_plot_df["analysis_time_run"].dropna().sort_values()
    if not full_sorted_time_run.empty:
        default_x_range = [full_sorted_time_run.iloc[0], full_sorted_time_run.iloc[-1]]

    plot_df = full_plot_df.copy()
    plot_df = plot_df.dropna(subset=[value_col])

    if plot_df.empty:
        return _build_no_data_figure(
            title=title,
            yaxis_title=yaxis_title,
            theme=theme,
            uirevision=uirevision,
            margin_bottom=margin_bottom,
            x_range=x_range or default_x_range,
        )

    # set limits on datapoints:
    # j target
    j_target = 3.0
    tol = 0.05
    j_low = j_target * (1 - tol)
    j_high = j_target * (1 + tol)

    j_l_target = 0.6
    tol_l = 0.05
    j_l_low = j_l_target * (1 - tol_l)
    j_l_high = j_l_target * (1 + tol_l)

    # p target (p_cat_out)
    p_target = 40.0
    tol = 0.05
    p_low = p_target * (1 - tol)
    p_high = p_target * (1 + tol)

    # t target (t_an_in)
    t_target = 70.0
    tol = 0.05
    t_low = t_target * (1 - tol)
    t_high = t_target * (1 + tol)

    x_col = "analysis_time_run"
    x_title = "Hours run [h]"
    scatter_mode = "markers"

    fig = go.Figure()
    trace_count = 0

    if not plot_df.empty and "order_id" in plot_df.columns:
        unique_order_ids = sorted(plot_df["order_id"].dropna().unique())

        for order_id in unique_order_ids:
            order_df = plot_df[plot_df["order_id"] == order_id].copy()
            order_df_3 = order_df[
                (order_df["j"] >= j_low)
                & (order_df["j"] <= j_high)
                & (order_df["p_cat_out"] >= p_low)
                & (order_df["p_cat_out"] <= p_high)
                & (order_df["t_an_in"] >= t_low)
                & (order_df["t_an_in"] <= t_high)
            ]
            order_df_06 = order_df[
                (order_df["j"] >= j_l_low)
                & (order_df["j"] <= j_l_high)
                & (order_df["p_cat_out"] >= p_low)
                & (order_df["p_cat_out"] <= p_high)
                & (order_df["t_an_in"] >= t_low)
                & (order_df["t_an_in"] <= t_high)
            ]

            if not order_df.empty:
                color = get_order_id_color(order_id, unique_order_ids)
                if order_df_3.empty:
                    continue
                # for h2 in o2 we want to show the 0.6 filtered data, for the rest the 3.0 filtered data
                if value_col == "c_h2ino2":
                    fig.add_trace(
                        go.Scatter(
                            x=order_df_06[x_col],
                            y=order_df_06[value_col],
                            mode=scatter_mode,
                            name=order_id,
                            marker=dict(size=8, color=color),
                            line=dict(width=2, color=color),
                            hovertemplate=(
                                f"Order ID: {order_id}<br>{x_title}: %{{x:.2f}}<br>{hover_label}: %{{y:.3f}}<extra></extra>"
                            ),
                        )
                    )
                else:
                    fig.add_trace(
                        go.Scatter(
                            x=order_df_3[x_col],
                            y=order_df_3[value_col],
                            mode=scatter_mode,
                            name=order_id,
                            marker=dict(size=8, color=color),
                            line=dict(width=2, color=color),
                            hovertemplate=(
                                f"Order ID: {order_id}<br>{x_title}: %{{x:.2f}}<br>{hover_label}: %{{y:.3f}}<extra></extra>"
                            ),
                        )
                    )
                trace_count += 1

    if trace_count == 0:
        return _build_no_data_figure(
            title=title,
            yaxis_title=yaxis_title,
            theme=theme,
            uirevision=uirevision,
            margin_bottom=margin_bottom,
        )

    if target_line_function is not None:
        if not full_sorted_time_run.empty:
            fig.add_trace(
                go.Scattergl(
                    x=full_sorted_time_run,
                    y=target_line_function(full_sorted_time_run),
                    mode="lines",
                    line=dict(color="green", width=2, dash="dash"),
                    name=target_line_name or "Target line",
                ),
            )

    is_dark = theme == "dark"

    layout_dict = dict(
        xaxis_title=x_title,
        yaxis_title=yaxis_title,
        margin=dict(l=40, r=20, t=32, b=margin_bottom),
        showlegend=True,
        uirevision=uirevision,
    )
    if yaxis_range is not None:
        layout_dict["yaxis"] = dict(range=yaxis_range)
    fig.update_layout(**layout_dict)
    if x_range:
        fig.update_xaxes(range=x_range)
    elif reset_autorange:
        fig.update_xaxes(autorange=True)
    elif default_x_range:
        fig.update_xaxes(range=default_x_range)
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
        xaxis_title="Hours run [h]",
        yaxis_title="uCell",
    )

    fig_h2_in_o2 = go.Figure()
    fig_h2_in_o2.update_layout(
        title="c_h2_ino2",
        xaxis_title="Hours run [h]",
        yaxis_title="c_h2_ino2 [vol%]",
    )

    fig_o2_in_h2 = go.Figure()
    fig_o2_in_h2.update_layout(
        title="c_o2_inh2",
        xaxis_title="Hours run [h]",
        yaxis_title="c_o2_inh2 [vol%]",
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
                                "Total runtime for GEN 1 Proto 1 stacks by sample name (based on cloud data)",
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
                                                dmc.InputWrapper(
                                                    dcc.Dropdown(
                                                        id=f"{ns}-trackrecord-sample-filter",
                                                        placeholder="Select a sample name",
                                                        clearable=True,
                                                        searchable=True,
                                                        className="trackrecord-filter-dropdown",
                                                        style=FILTER_DROPDOWN_STYLE,
                                                    ),
                                                    label="Sample name",
                                                    htmlFor=f"{ns}-trackrecord-sample-filter",
                                                    className="dmc",
                                                    styles={"label": {"marginBottom": "6px"}},
                                                    style=FILTER_WRAPPER_STYLE,
                                                ),
                                                dmc.InputWrapper(
                                                    dcc.Dropdown(
                                                        id=f"{ns}-trackrecord-order-filter",
                                                        placeholder="Select one or more order IDs",
                                                        multi=True,
                                                        className="trackrecord-filter-dropdown",
                                                        style=FILTER_DROPDOWN_STYLE,
                                                    ),
                                                    label="Order IDs",
                                                    htmlFor=f"{ns}-trackrecord-order-filter",
                                                    className="dmc",
                                                    styles={"label": {"marginBottom": "6px"}},
                                                    style=FILTER_WRAPPER_STYLE,
                                                ),
                                                dmc.Stack(
                                                    gap=4,
                                                    style={"width": "140px", "minWidth": "140px"},
                                                    children=[
                                                        dmc.Text("uCell y limit", fw=500, size="sm", ta="center"),
                                                        dmc.Group(
                                                            gap="xs",
                                                            grow=True,
                                                            children=[
                                                                dmc.NumberInput(
                                                                    id=f"{ns}-trackrecord-ucell-y-min",
                                                                    placeholder="min",
                                                                    size="sm",
                                                                    hideControls=True,
                                                                    styles=LIMIT_INPUT_STYLES,
                                                                    style={"width": "100%"},
                                                                ),
                                                                dmc.NumberInput(
                                                                    id=f"{ns}-trackrecord-ucell-y-max",
                                                                    placeholder="max",
                                                                    size="sm",
                                                                    hideControls=True,
                                                                    styles=LIMIT_INPUT_STYLES,
                                                                    style={"width": "100%"},
                                                                ),
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                                dmc.Stack(
                                                    gap=4,
                                                    style={"width": "140px", "minWidth": "140px"},
                                                    children=[
                                                        dmc.Text("H2 in O2 y limit", fw=500, size="sm", ta="center"),
                                                        dmc.Group(
                                                            gap="xs",
                                                            grow=True,
                                                            children=[
                                                                dmc.NumberInput(
                                                                    id=f"{ns}-trackrecord-h2ino2-y-min",
                                                                    placeholder="min",
                                                                    size="sm",
                                                                    hideControls=True,
                                                                    styles=LIMIT_INPUT_STYLES,
                                                                    style={"width": "100%"},
                                                                ),
                                                                dmc.NumberInput(
                                                                    id=f"{ns}-trackrecord-h2ino2-y-max",
                                                                    placeholder="max",
                                                                    size="sm",
                                                                    hideControls=True,
                                                                    styles=LIMIT_INPUT_STYLES,
                                                                    style={"width": "100%"},
                                                                ),
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                                dmc.Stack(
                                                    gap=4,
                                                    style={"width": "140px", "minWidth": "140px"},
                                                    children=[
                                                        dmc.Text("O2 in H2 y limit", fw=500, size="sm", ta="center"),
                                                        dmc.Group(
                                                            gap="xs",
                                                            grow=True,
                                                            children=[
                                                                dmc.NumberInput(
                                                                    id=f"{ns}-trackrecord-o2inh2-y-min",
                                                                    placeholder="min",
                                                                    size="sm",
                                                                    hideControls=True,
                                                                    styles=LIMIT_INPUT_STYLES,
                                                                    style={"width": "100%"},
                                                                ),
                                                                dmc.NumberInput(
                                                                    id=f"{ns}-trackrecord-o2inh2-y-max",
                                                                    placeholder="max",
                                                                    size="sm",
                                                                    hideControls=True,
                                                                    styles=LIMIT_INPUT_STYLES,
                                                                    style={"width": "100%"},
                                                                ),
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                                dmc.Button(
                                                    "Reset limits",
                                                    id=f"{ns}-trackrecord-reset-limits",
                                                    variant="light",
                                                    size="sm",
                                                    style={"alignSelf": "end", "marginBottom": "1px"},
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
                                                        id=f"{ns}-trackrecord-c-h2-ino2-plot",
                                                        figure=fig_h2_in_o2,
                                                        config={"responsive": True},
                                                        style={
                                                            "width": "100%",
                                                            "height": "280px",
                                                        },
                                                    ),
                                                    dcc.Graph(
                                                        id=f"{ns}-trackrecord-c-o2-inh2-plot",
                                                        figure=fig_o2_in_h2,
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
        Output(f"{ns}-trackrecord-sample-filter", "options"),
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
            )
        except Exception:
            return []

        df = _ensure_columns(df, DETAIL_COLS)
        sort_candidates = ["runtime_hour", "hours_run", "run_hours"]
        sort_col = next((col for col in sort_candidates if col in df.columns), None)
        if sort_col:
            df[sort_col] = pd.to_numeric(df[sort_col], errors="coerce")
            df = df.sort_values(sort_col, ascending=True, na_position="last")
        return df.to_dict("records")

    @callback(
        Output(f"{ns}-trackrecord-order-filter", "options"),
        Output(f"{ns}-trackrecord-order-filter", "value"),
        Input(f"{ns}-trackrecord-detail-data", "data"),
        State(f"{ns}-trackrecord-order-filter", "value"),
    )
    def populate_order_filter(detail_rows, current_order_ids):
        df = _ensure_columns(pd.DataFrame(detail_rows or []), DETAIL_COLS)
        if df.empty:
            return [], []

        df["order_id"] = df["order_id"].fillna("Unknown").astype(str).str.strip()
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        order_rank = (
            df.groupby("order_id", dropna=False)["time"]
            .min()
            .reset_index()
        )
        order_rank["sort_time"] = order_rank["time"].fillna(pd.Timestamp.max)
        order_rank = order_rank.sort_values(["sort_time", "order_id"])
        order_ids = order_rank["order_id"].astype(str).tolist()
        options = [{"label": order_id, "value": order_id} for order_id in order_ids]

        if current_order_ids:
            valid_values = set(order_ids)
            selected = [str(order_id) for order_id in current_order_ids if str(order_id) in valid_values]
            if selected:
                return options, selected

        return options, order_ids

    @callback(
        Output(f"{ns}-trackrecord-ucell-y-min", "value"),
        Output(f"{ns}-trackrecord-ucell-y-max", "value"),
        Output(f"{ns}-trackrecord-h2ino2-y-min", "value"),
        Output(f"{ns}-trackrecord-h2ino2-y-max", "value"),
        Output(f"{ns}-trackrecord-o2inh2-y-min", "value"),
        Output(f"{ns}-trackrecord-o2inh2-y-max", "value"),
        Input(f"{ns}-trackrecord-reset-limits", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_y_limits(n_clicks):
        if not n_clicks:
            return no_update, no_update, no_update, no_update, no_update, no_update
        return None, None, None, None, None, None

    @callback(
        Output(f"{ns}-trackrecord-uCell-plot", "figure"),
        Output(f"{ns}-trackrecord-c-h2-ino2-plot", "figure"),
        Output(f"{ns}-trackrecord-c-o2-inh2-plot", "figure"),
        Input(f"{ns}-trackrecord-detail-data", "data"),
        Input(f"{ns}-trackrecord-sample-filter", "value"),
        Input(f"{ns}-trackrecord-order-filter", "value"),
        Input("theme-store", "data"),
        Input(f"{ns}-trackrecord-ucell-y-min", "value"),
        Input(f"{ns}-trackrecord-ucell-y-max", "value"),
        Input(f"{ns}-trackrecord-h2ino2-y-min", "value"),
        Input(f"{ns}-trackrecord-h2ino2-y-max", "value"),
        Input(f"{ns}-trackrecord-o2inh2-y-min", "value"),
        Input(f"{ns}-trackrecord-o2inh2-y-max", "value"),
        Input(f"{ns}-trackrecord-uCell-plot", "relayoutData"),
        Input(f"{ns}-trackrecord-c-h2-ino2-plot", "relayoutData"),
        Input(f"{ns}-trackrecord-c-o2-inh2-plot", "relayoutData"),
    )
    def update_detail_plots(
        detail_rows,
        sample_name,
        selected_order_ids,
        theme,
        ucell_y_min,
        ucell_y_max,
        h2ino2_y_min,
        h2ino2_y_max,
        o2inh2_y_min,
        o2inh2_y_max,
        relayout_u,
        relayout_h2,
        relayout_o2,
    ):
        df = pd.DataFrame(detail_rows or [])
        df = _ensure_columns(df, DETAIL_COLS)
        normalized_order_ids = [str(order_id) for order_id in (selected_order_ids or []) if str(order_id).strip()]
        ucell_y_range = _coerce_axis_range(ucell_y_min, ucell_y_max)
        h2ino2_y_range = _coerce_axis_range(h2ino2_y_min, h2ino2_y_max)
        o2inh2_y_range = _coerce_axis_range(o2inh2_y_min, o2inh2_y_max)
        y_limit_key = "|".join(
            [
                f"ucell:{ucell_y_range[0]}:{ucell_y_range[1]}" if ucell_y_range else "ucell:auto",
                f"h2:{h2ino2_y_range[0]}:{h2ino2_y_range[1]}" if h2ino2_y_range else "h2:auto",
                f"o2:{o2inh2_y_range[0]}:{o2inh2_y_range[1]}" if o2inh2_y_range else "o2:auto",
            ]
        )
        uirevision = f"{ns}-trackrecord-{sample_name or 'none'}-{'|'.join(normalized_order_ids) or 'all'}-{y_limit_key}"

        x_range = None
        reset_autorange = False
        ctx = callback_context
        if ctx.triggered and "relayoutData" in ctx.triggered[0]["prop_id"]:
            relayout = ctx.triggered[0]["value"] or {}
            if "xaxis.range[0]" in relayout:
                x_range = [relayout["xaxis.range[0]"], relayout["xaxis.range[1]"]]
            elif relayout.get("xaxis.autorange") is True:
                reset_autorange = True

        ucell_fig = build_detail_plot(
            df=df,
            title="uCell",
            value_col="u_cell_avg",
            yaxis_title="uCell [V]",
            hover_label="uCell [V]",
            yaxis_range=ucell_y_range,
            theme=theme,
            uirevision=uirevision,
            selected_order_ids=normalized_order_ids,
            margin_bottom=0,
            target_line_function=_ucell_target_line,
            target_line_name="uCell target line 1.5%",
            x_range=x_range,
            reset_autorange=reset_autorange,
        )

        h2_in_o2_fig = build_detail_plot(
            df=df,
            title="c_h2_ino2",
            value_col="c_h2ino2",
            yaxis_title="H2 in O2 [vol%]",
            hover_label="H2 in O2 [vol%]",
            yaxis_range=h2ino2_y_range,
            theme=theme,
            uirevision=f"{uirevision}-c_h2_ino2",
            selected_order_ids=normalized_order_ids,
            margin_bottom=0,
            target_line_function=_h2_in_o2_target_line,
            target_line_name="H2 in O2 target line",
            x_range=x_range,
            reset_autorange=reset_autorange,
        )

        o2_in_h2_fig = build_detail_plot(
            df=df,
            title="c_o2_inh2",
            value_col="c_o2inh2",
            yaxis_title="O2 in H2 [ppm]",
            hover_label="O2 in H2 [ppm]",
            yaxis_range=o2inh2_y_range,
            theme=theme,
            uirevision=f"{uirevision}-c_o2_inh2",
            selected_order_ids=normalized_order_ids,
            margin_bottom=0,
            target_line_function=_o2_in_h2_target_line,
            target_line_name="O2 in H2 target line",
            x_range=x_range,
            reset_autorange=reset_autorange,
        )
        return ucell_fig, h2_in_o2_fig, o2_in_h2_fig

    return layout
