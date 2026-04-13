from datetime import datetime, timedelta

from dash import (
    callback,
    dcc,
    Input,
    Output,
    State,
    no_update,
    register_page,
)
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from services.backend_service import get_metadata, get_timeseries

register_page(
    __name__,
    path="/sherlock/data-exploration/timeseries-overview",
    title="HOLMES - Sherlock - Timeseries Overview",
)

DEFAULT_START = datetime.utcnow() - timedelta(days=30)
DEFAULT_END = datetime.utcnow()
REQUEST_TIME_COLUMN = "time"
PLOT_TIME_COLUMN = "bucket_start"
TARGET_POINTS = 1200

CORE_SIGNALS = [
    "jStck",
    "uStck",
    "pAndeIn",
    "pAndeOut",
    "mfH2Out",
    "tAndeIn",
    "tAndeOut",
]

SIGNAL_META = {
    "jStck": ("Current Density", "A/cm^2"),
    "uStck": ("Stack Voltage", "V"),
    "pAndeIn": ("Anode Pressure In", "bar"),
    "pAndeOut": ("Anode Pressure Out", "bar"),
    "mfH2Out": ("H2 Mass Flow Out", "kg/s"),
    "tAndeIn": ("Anode Temp In", "degC"),
    "tAndeOut": ("Anode Temp Out", "degC"),
}

EXTRA_SIGNALS = [
    "cndAndeIn",
    "cndAndeOut",
    "cndCtdeIn",
    "cndCtdeOut",
    "concH2O2",
    "concH2StckAmb",
    "concO2H2",
    "iStckSp",
    "mfO2Out",
    "pAndeOutSp",
    "pCtdeIn",
    "pCtdeOut",
    "pCtdeOutSp",
    "tAmb",
    "tAndeInSp",
    "tCtdeIn",
    "tCtdeOut",
    "vfAndeIn",
    "vfAndeInSp",
    "vfAndeOut",
    "vfCtdeIn",
    "vfCtdeInSp",
    "iStck",
    "uCell",
]

SENSOR_TITLES = {
    "iStck": "Stack Current (iStck)",
    "iStckSp": "Stack Current Setpoint (iStckSp)",
    "jStck": "Current Density (jStck)",
    "uStck": "Stack Voltage (uStck)",
    "uCell": "Cell Voltage (uCell)",
    "pAndeIn": "Anode Inlet Pressure (pAndeIn)",
    "pAndeOut": "Anode Outlet Pressure (pAndeOut)",
    "pAndeOutSp": "Anode Outlet Pressure Setpoint (pAndeOutSp)",
    "pCtdeIn": "Cathode Inlet Pressure (pCtdeIn)",
    "pCtdeOut": "Cathode Outlet Pressure (pCtdeOut)",
    "pCtdeOutSp": "Cathode Outlet Pressure Setpoint (pCtdeOutSp)",
    "tAmb": "Ambient Temperature (tAmb)",
    "tAndeIn": "Anode Inlet Temperature (tAndeIn)",
    "tAndeInSp": "Anode Inlet Temperature Setpoint (tAndeInSp)",
    "tAndeOut": "Anode Outlet Temperature (tAndeOut)",
    "tCtdeIn": "Cathode Inlet Temperature (tCtdeIn)",
    "tCtdeOut": "Cathode Outlet Temperature (tCtdeOut)",
    "vfAndeIn": "Anode Inlet Volume Flow (vfAndeIn)",
    "vfAndeInSp": "Anode Inlet Volume Flow Setpoint (vfAndeInSp)",
    "vfAndeOut": "Anode Outlet Volume Flow (vfAndeOut)",
    "vfCtdeIn": "Cathode Inlet Volume Flow (vfCtdeIn)",
    "vfCtdeInSp": "Cathode Inlet Volume Flow Setpoint (vfCtdeInSp)",
    "mfH2Out": "Hydrogen Outlet Mass Flow (mfH2Out)",
    "mfO2Out": "Oxygen Outlet Mass Flow (mfO2Out)",
    "cndAndeIn": "Anode Inlet Conductivity (cndAndeIn)",
    "cndAndeOut": "Anode Outlet Conductivity (cndAndeOut)",
    "cndCtdeIn": "Cathode Inlet Conductivity (cndCtdeIn)",
    "cndCtdeOut": "Cathode Outlet Conductivity (cndCtdeOut)",
    "concH2O2": "Hydrogen Peroxide Concentration (concH2O2)",
    "concH2StckAmb": "Hydrogen Stack Ambient Concentration (concH2StckAmb)",
    "concO2H2": "Oxygen in Hydrogen Concentration (concO2H2)",
}

SENSOR_UNITS = {
    "iStck": "A",
    "iStckSp": "A",
    "jStck": "A/cm^2",
    "uStck": "V",
    "uCell": "V",
    "pAndeIn": "bar",
    "pAndeOut": "bar",
    "pAndeOutSp": "bar",
    "pCtdeIn": "bar",
    "pCtdeOut": "bar",
    "pCtdeOutSp": "bar",
    "tAmb": "degC",
    "tAndeIn": "degC",
    "tAndeInSp": "degC",
    "tAndeOut": "degC",
    "tCtdeIn": "degC",
    "tCtdeOut": "degC",
    "vfAndeIn": "L/min",
    "vfAndeInSp": "L/min",
    "vfAndeOut": "L/min",
    "vfCtdeIn": "L/min",
    "vfCtdeInSp": "L/min",
    "mfH2Out": "kg/s",
    "mfO2Out": "kg/s",
    "cndAndeIn": "uS/cm",
    "cndAndeOut": "uS/cm",
    "cndCtdeIn": "uS/cm",
    "cndCtdeOut": "uS/cm",
    "concH2O2": "%",
    "concH2StckAmb": "%",
    "concO2H2": "%",
}

DEFAULT_SENSOR_NAMES = [
    f"{label} ({key})"
    for key, (label, _unit) in SIGNAL_META.items()
]

USAGE_BLOCKQUOTE_TEXT = [
    "Choose an order to load the default timeseries view. Add testrig, sample, or cell filters to narrow the result.",
    "Use Additional Signals to extend the plot and switch between average, minimum, and maximum values in the header.",
    "Zoom or pan the chart to reload the selected time window.",
    "Default signals: " + ", ".join(DEFAULT_SENSOR_NAMES) + ".",
]


def _empty_figure(theme: str, message: str = "Select filters to view timeseries data") -> go.Figure:
    is_dark = theme == "dark"
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark" if is_dark else "plotly",
        margin=dict(t=40, l=80, r=30, b=60),
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
    return fig


def _to_options(values: list) -> list[dict]:
    return [{"label": str(v), "value": v} for v in values]


def _read_viewport(relayout_data: dict | None) -> tuple[str | None, str | None]:
    if not isinstance(relayout_data, dict):
        return None, None
    if "xaxis.range[0]" in relayout_data and "xaxis.range[1]" in relayout_data:
        return relayout_data.get("xaxis.range[0]"), relayout_data.get("xaxis.range[1]")
    if "xaxis.range" in relayout_data and isinstance(relayout_data["xaxis.range"], list):
        rng = relayout_data["xaxis.range"]
        if len(rng) == 2:
            return rng[0], rng[1]
    if relayout_data.get("xaxis.autorange"):
        return None, None
    return None, None


_PLOT_COLORS = [
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


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    clean = hex_color.lstrip("#")
    if len(clean) != 6:
        return f"rgba(31,119,180,{alpha})"
    red = int(clean[0:2], 16)
    green = int(clean[2:4], 16)
    blue = int(clean[4:6], 16)
    return f"rgba({red},{green},{blue},{alpha})"


def _resolve_metric_column(df: pd.DataFrame, signal: str, metric: str) -> str | None:
    preferred = f"{signal}_{metric}"
    if preferred in df.columns:
        return preferred
    if metric == "avg" and signal in df.columns:
        return signal
    return None


def _series_has_data(df: pd.DataFrame, column: str | None) -> bool:
    if not column or column not in df.columns:
        return False
    return df[column].notna().any()


def _signal_has_data(df: pd.DataFrame, signal: str, metric: str) -> bool:
    if metric == "all":
        has_avg = _series_has_data(df, _resolve_metric_column(df, signal, "avg"))
        has_min = _series_has_data(df, _resolve_metric_column(df, signal, "min"))
        has_max = _series_has_data(df, _resolve_metric_column(df, signal, "max"))
        return has_avg or (has_min and has_max)
    return _series_has_data(df, _resolve_metric_column(df, signal, metric))


def _build_plot_groups(signals: list[str], plot_mode: str) -> list[tuple[str, str, list[str]]]:
    if plot_mode != "stacked":
        return [
            (SENSOR_TITLES.get(signal, signal), SENSOR_UNITS.get(signal, ""), [signal])
            for signal in signals
        ]

    grouped: dict[str, list[str]] = {}
    for signal in signals:
        unit = SENSOR_UNITS.get(signal, "value")
        grouped.setdefault(unit, []).append(signal)

    return [
        (f"{unit} signals", unit, grouped[unit])
        for unit in grouped
    ]


def _legend_ref(row_index: int) -> str:
    return "legend" if row_index == 1 else f"legend{row_index}"


def _build_figure(
    df: pd.DataFrame,
    signals: list[str],
    theme: str,
    metric: str = "avg",
    plot_mode: str = "isolated",
) -> go.Figure:
    if df.empty:
        return _empty_figure(theme, "No data for selected filters")

    if PLOT_TIME_COLUMN not in df.columns:
        return _empty_figure(theme, "The response does not contain a time column")

    is_dark = theme == "dark"
    template = "plotly_dark" if is_dark else "plotly"

    df = df.copy()
    df[PLOT_TIME_COLUMN] = pd.to_datetime(df[PLOT_TIME_COLUMN], errors="coerce")
    df = df.dropna(subset=[PLOT_TIME_COLUMN]).sort_values(PLOT_TIME_COLUMN)
    if df.empty:
        return _empty_figure(theme, "No data for selected filters")

    safe_signals = [signal for signal in signals if _signal_has_data(df, signal, metric)]
    if not safe_signals:
        return _empty_figure(theme, "No plottable data for selected signals")

    groups = _build_plot_groups(safe_signals, plot_mode)
    if not groups:
        return _empty_figure(theme, "No plottable data for selected signals")

    n_groups = len(groups)
    is_stacked = plot_mode == "stacked"
    vertical_spacing = 0.09 if is_stacked else 0.04
    total_height = max(360, 270 * n_groups + (56 * n_groups if is_stacked else 0))

    fig = make_subplots(
        rows=n_groups,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=vertical_spacing,
        subplot_titles=[title for title, _unit, _signals in groups],
    )

    color_index = 0
    for row_index, (_title, unit, group_signals) in enumerate(groups, start=1):
        leg_ref = _legend_ref(row_index)
        show_legend = plot_mode == "stacked"
        legend_kwargs = {"legend": leg_ref} if show_legend else {}

        for signal in group_signals:
            color = _PLOT_COLORS[color_index % len(_PLOT_COLORS)]
            color_index += 1
            signal_title = SENSOR_TITLES.get(signal, signal)
            signal_group = f"row{row_index}:{signal}"

            if metric == "all":
                min_col = _resolve_metric_column(df, signal, "min")
                max_col = _resolve_metric_column(df, signal, "max")
                avg_col = _resolve_metric_column(df, signal, "avg")

                has_min = _series_has_data(df, min_col)
                has_max = _series_has_data(df, max_col)
                has_avg = _series_has_data(df, avg_col)

                if has_min and has_max:
                    fig.add_trace(
                        go.Scatter(
                            x=df[PLOT_TIME_COLUMN],
                            y=df[min_col],
                            mode="lines",
                            line=dict(width=0, color=color),
                            showlegend=False,
                            hoverinfo="skip",
                            legendgroup=signal_group,
                            name=f"{signal_title} min",
                            **legend_kwargs,
                        ),
                        row=row_index,
                        col=1,
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=df[PLOT_TIME_COLUMN],
                            y=df[max_col],
                            mode="lines",
                            line=dict(width=0, color=color),
                            fill="tonexty",
                            fillcolor=_hex_to_rgba(color, 0.18),
                            showlegend=False,
                            hoverinfo="skip",
                            legendgroup=signal_group,
                            name=f"{signal_title} max",
                            **legend_kwargs,
                        ),
                        row=row_index,
                        col=1,
                    )

                if has_avg:
                    fig.add_trace(
                        go.Scatter(
                            x=df[PLOT_TIME_COLUMN],
                            y=df[avg_col],
                            mode="lines",
                            name=signal_title,
                            line=dict(width=2.8, color=color),
                            showlegend=show_legend,
                            legendgroup=signal_group,
                            **legend_kwargs,
                        ),
                        row=row_index,
                        col=1,
                    )
                continue

            value_col = _resolve_metric_column(df, signal, metric)
            if not _series_has_data(df, value_col):
                continue

            fig.add_trace(
                go.Scatter(
                    x=df[PLOT_TIME_COLUMN],
                    y=df[value_col],
                    mode="lines",
                    name=signal_title,
                    line=dict(width=1.8, color=color),
                    showlegend=show_legend,
                    legendgroup=signal_group,
                    **legend_kwargs,
                ),
                row=row_index,
                col=1,
            )

        fig.update_yaxes(
            title_text=unit,
            row=row_index,
            col=1,
            gridcolor="rgba(255,255,255,0.15)" if is_dark else "rgba(0,0,0,0.08)",
        )

    fig.update_xaxes(
        title_text="Time",
        title_standoff=42,
        row=n_groups,
        col=1,
        gridcolor="rgba(255,255,255,0.15)" if is_dark else "rgba(0,0,0,0.08)",
    )

    layout_updates: dict = dict(
        template=template,
        height=total_height,
        margin=dict(t=48, l=80, r=30, b=520 if is_stacked else 60),
        showlegend=is_stacked,
    )

    # Per-subplot legends: position each legend in the gap below its subplot.
    if is_stacked:
        legend_bg = "rgba(255,255,255,0.06)" if is_dark else "rgba(0,0,0,0.03)"
        row_domains = [
            getattr(fig.layout, "yaxis" if idx == 1 else f"yaxis{idx}").domain
            for idx in range(1, n_groups + 1)
        ]
        for row_index in range(1, n_groups + 1):
            domain = row_domains[row_index - 1]
            if row_index < n_groups:
                # Keep legend close to the current subplot bottom, away from the
                # next subplot title at the top of the following domain.
                legend_y = max(0.02, domain[0] - 0.008)
                legend_yanchor = "top"
            else:
                # Keep last legend directly below the plot area (like other rows).
                # The increased x-axis title standoff and bottom margin prevent
                # collisions with the shared x-axis title.
                legend_y = max(0.01, domain[0] - 0.06)
                legend_yanchor = "top"

            layout_updates[_legend_ref(row_index)] = dict(
                x=0.5,
                xanchor="center",
                y=legend_y,
                yanchor=legend_yanchor,
                orientation="h",
                tracegroupgap=6,
                font=dict(size=10),
                bgcolor=legend_bg,
                borderwidth=0,
                groupclick="togglegroup",
            )

    fig.update_layout(**layout_updates)
    return fig

def _resolve_time_column(df: pd.DataFrame) -> str | None:
    for candidate in ("bucket_start", "time", "ts"):
        if candidate in df.columns:
            return candidate
    return None


def _humanize_timestamp(value: str | None) -> str:
    if value in (None, ""):
        return "-"
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return str(value)
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC")


def _humanize_bucket(bucket_seconds: int | None, bucket_label: str | None = None) -> str | None:
    if bucket_label:
        return bucket_label
    if bucket_seconds is None:
        return None
    if bucket_seconds <= 0:
        return f"{bucket_seconds}s"
    days, rem = divmod(bucket_seconds, 24 * 60 * 60)
    hours, rem = divmod(rem, 60 * 60)
    minutes, seconds = divmod(rem, 60)
    if days and not (hours or minutes or seconds):
        return f"{days}d"
    if hours and not (minutes or seconds):
        return f"{hours}h"
    if minutes and not seconds:
        return f"{minutes}m"
    if minutes or seconds:
        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds:
            parts.append(f"{seconds}s")
        return " ".join(parts)
    return f"{bucket_seconds}s"


def timeseries_overview_layout():
    return dmc.Container(
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
                                    dmc.Title("Timeseries Overview", order=2),
                                    dmc.ActionIcon(
                                        DashIconify(icon="material-symbols:info-outline", width=20),
                                        id="timeseries-usage-toggle",
                                        variant="subtle",
                                        color="blue",
                                        size="md",
                                        radius="xl",
                                    ),
                                ],
                            ),
                            dmc.Text(
                                "Review key stack signals for a selected order and refine the view with filters, extra signals, and time-range zooming.",
                                c="dimmed",
                            ),
                            dmc.Collapse(
                                dmc.Blockquote(
                                    dmc.List(
                                        withPadding=False,
                                        children=[dmc.ListItem(item) for item in USAGE_BLOCKQUOTE_TEXT],
                                    ),
                                    color="blue",
                                ),
                                opened=True,
                                id="timeseries-usage-collapse",
                            ),
                        ],
                    ),
                    dcc.Store(id="timeseries-usage-open", data=True),
                    dcc.Store(id="timeseries-metadata-store"),
                    dcc.Store(id="timeseries-viewport-store", data={"start": None, "end": None}),
                    dcc.Store(id="timeseries-init-trigger", data=True),
                    dmc.Paper(
                        withBorder=True,
                        p="md",
                        radius="md",
                        children=[
                            dmc.SimpleGrid(
                                cols={"base": 1, "sm": 2, "lg": 3},
                                spacing="md",
                                verticalSpacing="md",
                                children=[
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="timeseries-order-id-filter",
                                            options=[],
                                            value=None,
                                            clearable=False,
                                            searchable=True,
                                            placeholder="Select order ID",
                                            style={"width": "100%"},
                                        ),
                                        label="Order ID",
                                        htmlFor="timeseries-order-id-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="timeseries-testrig-id-filter",
                                            options=[],
                                            value=None,
                                            clearable=True,
                                            searchable=True,
                                            placeholder="Select testrig ID",
                                            style={"width": "100%"},
                                        ),
                                        label="Testrig ID",
                                        htmlFor="timeseries-testrig-id-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="timeseries-sample-name-filter",
                                            options=[],
                                            value=None,
                                            clearable=True,
                                            searchable=True,
                                            placeholder="Select sample name",
                                            style={"width": "100%"},
                                        ),
                                        label="Sample Name",
                                        htmlFor="timeseries-sample-name-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="timeseries-number-of-cells-filter",
                                            options=[],
                                            value=None,
                                            clearable=True,
                                            searchable=True,
                                            placeholder="Select number of cells",
                                            style={"width": "100%"},
                                        ),
                                        label="Number of Cells",
                                        htmlFor="timeseries-number-of-cells-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="timeseries-extra-signals",
                                            options=_to_options(EXTRA_SIGNALS),
                                            value=[],
                                            multi=True,
                                            clearable=True,
                                            searchable=True,
                                            placeholder="Select additional signals",
                                            style={"width": "100%"},
                                        ),
                                        label="Additional Signals",
                                        htmlFor="timeseries-extra-signals",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                    ),
                                    dmc.Stack(
                                        gap=6,
                                        justify="flex-end",
                                        children=[
                                            dmc.Text("Download", fw=600, size="sm"),
                                            dmc.Button(
                                                "Download CSV (disabled)",
                                                id="timeseries-download-btn",
                                                disabled=True,
                                                variant="light",
                                            ),
                                        ],
                                    ),
                                ],
                            )
                        ],
                    ),
                    dmc.Paper(
                        withBorder=True,
                        p="md",
                        radius="md",
                        children=[
                            dmc.Group(
                                justify="space-between",
                                children=[
                                    dmc.Text(id="timeseries-status-text", c="dimmed", size="sm"),
                                    dmc.Group(
                                        gap="sm",
                                        align="center",
                                        children=[
                                            dmc.Badge(id="timeseries-meta-badge", variant="light", color="blue"),
                                            dmc.Text("Value", size="sm", c="dimmed", fw=600),
                                            dmc.SegmentedControl(
                                                id="timeseries-metric-selector",
                                                data=[
                                                    {"label": "All", "value": "all"},
                                                    {"label": "Avg", "value": "avg"},
                                                    {"label": "Min", "value": "min"},
                                                    {"label": "Max", "value": "max"},
                                                ],
                                                value="all",
                                                size="xs",
                                                radius="md",
                                                style={"minWidth": "220px"},
                                            ),
                                            dmc.Text("Layout", size="sm", c="dimmed", fw=600),
                                            dmc.SegmentedControl(
                                                id="timeseries-plot-mode-selector",
                                                data=[
                                                    {"label": "Isolated", "value": "isolated"},
                                                    {"label": "Stacked", "value": "stacked"},
                                                ],
                                                value="isolated",
                                                size="xs",
                                                radius="md",
                                                style={"minWidth": "190px"},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            dmc.Space(h="sm"),
                            dcc.Loading(
                                id="timeseries-graph-loading",
                                type="default",
                                children=[
                                    dcc.Graph(
                                        id="timeseries-graph",
                                        figure=_empty_figure("light", "Loading metadata..."),
                                        config={"responsive": True, "displaylogo": False},
                                        style={"width": "100%"},
                                    )
                                ],
                            ),
                        ],
                    ),
                ],
            )
        ],
    )


layout = timeseries_overview_layout


@callback(
    Output("timeseries-usage-open", "data"),
    Input("timeseries-usage-toggle", "n_clicks"),
    State("timeseries-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage_blockquote(n_clicks, is_open):
    if n_clicks is None:
        return no_update
    return not bool(is_open)


@callback(
    Output("timeseries-usage-collapse", "opened"),
    Input("timeseries-usage-open", "data"),
)
def sync_usage_blockquote(is_open):
    return bool(is_open)


@callback(
    Output("timeseries-metadata-store", "data"),
    Input("timeseries-init-trigger", "data"),
)
def load_timeseries_metadata(_):
    rows = get_metadata("sherlock", "timeseries_exp")
    return rows or []


@callback(
    Output("timeseries-order-id-filter", "options"),
    Output("timeseries-order-id-filter", "value"),
    Output("timeseries-testrig-id-filter", "options"),
    Output("timeseries-sample-name-filter", "options"),
    Output("timeseries-number-of-cells-filter", "options"),
    Input("timeseries-metadata-store", "data"),
)
def populate_filter_options(metadata_rows):
    if not metadata_rows:
        return [], None, [], [], []

    df = pd.DataFrame(metadata_rows)

    order_values = sorted(df["order_id"].dropna().unique().tolist(), reverse=True) if "order_id" in df.columns else []
    testrig_values = sorted(df["testrig_id"].dropna().unique().tolist()) if "testrig_id" in df.columns else []
    sample_values = sorted(df["sample_name"].dropna().unique().tolist()) if "sample_name" in df.columns else []

    if "number_of_cells" in df.columns:
        cell_series = (
            df["number_of_cells"]
            .dropna()
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
        )
        cell_values = sorted(cell_series.unique().tolist(), key=lambda x: (not str(x).isdigit(), str(x)))
    else:
        cell_values = []

    first_order = order_values[0] if order_values else None

    return (
        _to_options(order_values),
        first_order,
        _to_options(testrig_values),
        _to_options(sample_values),
        _to_options(cell_values),
    )


@callback(
    Output("timeseries-viewport-store", "data"),
    Input("timeseries-graph", "relayoutData"),
    State("timeseries-viewport-store", "data"),
    prevent_initial_call=True,
)
def update_viewport_store(relayout_data, current):
    start, end = _read_viewport(relayout_data)
    current = current or {"start": None, "end": None}
    if start == current.get("start") and end == current.get("end"):
        raise PreventUpdate
    return {"start": start, "end": end}


@callback(
    Output("timeseries-graph", "figure"),
    Output("timeseries-status-text", "children"),
    Output("timeseries-meta-badge", "children"),
    Input("timeseries-order-id-filter", "value"),
    Input("timeseries-testrig-id-filter", "value"),
    Input("timeseries-sample-name-filter", "value"),
    Input("timeseries-number-of-cells-filter", "value"),
    Input("timeseries-extra-signals", "value"),
    Input("timeseries-metric-selector", "value"),
    Input("timeseries-plot-mode-selector", "value"),
    Input("timeseries-viewport-store", "data"),
    Input("theme-store", "data"),
    prevent_initial_call=False,
)
def refresh_timeseries(
    order_id,
    testrig_id,
    sample_name,
    number_of_cells,
    extra_signals,
    metric,
    plot_mode,
    viewport,
    theme,
):
    theme = theme or "light"
    metric = metric or "all"
    plot_mode = plot_mode or "isolated"

    if order_id in (None, ""):
        fig = _empty_figure(theme, "No order ID available")
        return fig, "No order selected", "No request yet"

    signals = CORE_SIGNALS + (extra_signals or [])

    viewport = viewport or {"start": None, "end": None}
    start_value = viewport.get("start") or DEFAULT_START.isoformat()
    end_value = viewport.get("end") or DEFAULT_END.isoformat()

    filters = {"order_id": order_id}
    if testrig_id not in (None, ""):
        filters["testrig_id"] = testrig_id
    if sample_name not in (None, ""):
        filters["sample_name"] = sample_name
    if number_of_cells not in (None, ""):
        filters["number_of_cells"] = number_of_cells

    try:
        df = get_timeseries(
            space="sherlock",
            route_name="timeseries_exp",
            start=start_value,
            end=end_value,
            columns=signals,
            time_column=REQUEST_TIME_COLUMN,
            target_points=TARGET_POINTS,
            filters=filters,
        )
    except Exception as exc:
        fig = _empty_figure(theme, f"Request failed: {exc}")
        return fig, "Failed to load timeseries", "Request error"

    time_col = _resolve_time_column(df)
    if not time_col:
        fig = _empty_figure(theme, "No supported time column was returned")
        return fig, "No time axis available", "Request error"

    plot_df = df.rename(columns={time_col: PLOT_TIME_COLUMN}).copy()
    resolved_signals = [signal for signal in signals if _signal_has_data(plot_df, signal, metric)]

    fig = _build_figure(
        plot_df,
        resolved_signals,
        theme,
        metric=metric,
        plot_mode=plot_mode,
    )

    meta = df.attrs.get("meta", {}) if hasattr(df, "attrs") else {}
    returned_points = meta.get("returned_points", len(df))
    bucket_seconds = meta.get("bucket_seconds")
    bucket_label = meta.get("bucket_label")
    bucket_display = _humanize_bucket(bucket_seconds, bucket_label)
    effective_start = meta.get("effective_start", start_value)
    effective_end = meta.get("effective_end", end_value)
    readable_start = _humanize_timestamp(effective_start)
    readable_end = _humanize_timestamp(effective_end)

    status_text = (
        f"Viewport: {readable_start} to {readable_end}"
    )
    badge = (
        (f" | Bucket: {bucket_display}" if bucket_display else "")
    )

    return fig, status_text, badge
