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


def _build_figure(df: pd.DataFrame, signals: list[str], theme: str) -> go.Figure:
    if df.empty:
        return _empty_figure(theme, "No data for selected filters")

    if PLOT_TIME_COLUMN not in df.columns:
        return _empty_figure(theme, "The response does not contain a time column")

    is_dark = theme == "dark"
    template = "plotly_dark" if is_dark else "plotly"

    safe_signals = [s for s in signals if s in df.columns]
    if not safe_signals:
        return _empty_figure(theme, "No selected signal columns were returned")

    df = df.copy()
    df[PLOT_TIME_COLUMN] = pd.to_datetime(df[PLOT_TIME_COLUMN], errors="coerce")
    df = df.dropna(subset=[PLOT_TIME_COLUMN])

    fig = make_subplots(
        rows=len(safe_signals),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=[SENSOR_TITLES.get(s, s) for s in safe_signals],
    )

    for idx, signal in enumerate(safe_signals, start=1):
        fig.add_trace(
            go.Scatter(
                x=df[PLOT_TIME_COLUMN],
                y=df[signal],
                mode="lines",
                name=SENSOR_TITLES.get(signal, signal),
                line=dict(width=1.6),
            ),
            row=idx,
            col=1,
        )
        fig.update_yaxes(
            title_text=SENSOR_UNITS.get(signal, ""),
            row=idx,
            col=1,
            gridcolor="rgba(255,255,255,0.15)" if is_dark else "rgba(0,0,0,0.08)",
        )

    fig.update_xaxes(
        title_text="Time",
        row=len(safe_signals),
        col=1,
        gridcolor="rgba(255,255,255,0.15)" if is_dark else "rgba(0,0,0,0.08)",
    )

    fig.update_layout(
        template=template,
        height=max(360, 270 * len(safe_signals)),
        margin=dict(t=48, l=80, r=30, b=60),
        showlegend=False,
    )
    return fig


def _resolve_time_column(df: pd.DataFrame) -> str | None:
    for candidate in ("bucket_start", "time", "ts"):
        if candidate in df.columns:
            return candidate
    return None


def _resolve_value_column(df: pd.DataFrame, signal: str, metric: str) -> str | None:
    preferred = f"{signal}_{metric}"
    if preferred in df.columns:
        return preferred
    if signal in df.columns:
        return signal
    return None


def _humanize_timestamp(value: str | None) -> str:
    if value in (None, ""):
        return "-"
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return str(value)
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC")


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
                                                        {"label": "Avg", "value": "avg"},
                                                        {"label": "Min", "value": "min"},
                                                        {"label": "Max", "value": "max"},
                                                    ],
                                                    value="avg",
                                                    size="xs",
                                                    radius="md",
                                                    style={"minWidth": "170px"},
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
    viewport,
    theme,
):
    theme = theme or "light"
    metric = metric or "avg"

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

    plot_df = pd.DataFrame({time_col: df[time_col]})
    resolved_signals: list[str] = []
    for signal in signals:
        value_col = _resolve_value_column(df, signal, metric)
        if value_col:
            plot_df[signal] = df[value_col]
            resolved_signals.append(signal)

    fig = _build_figure(plot_df.rename(columns={time_col: PLOT_TIME_COLUMN}), resolved_signals, theme)

    meta = df.attrs.get("meta", {}) if hasattr(df, "attrs") else {}
    returned_points = meta.get("returned_points", len(df))
    bucket_seconds = meta.get("bucket_seconds")
    effective_start = meta.get("effective_start", start_value)
    effective_end = meta.get("effective_end", end_value)
    readable_start = _humanize_timestamp(effective_start)
    readable_end = _humanize_timestamp(effective_end)

    status_text = (
        f"Viewport: {readable_start} to {readable_end} | "
        f"Metric: {metric.upper()} | Signals: {len(resolved_signals)} | Rows: {len(df)}"
    )
    badge = (
        f"Points: {returned_points}"
        + (f" | Bucket: {bucket_seconds}s" if bucket_seconds is not None else "")
    )

    return fig, status_text, badge
