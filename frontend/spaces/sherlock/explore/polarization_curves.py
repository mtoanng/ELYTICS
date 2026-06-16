from dash import (
    dcc,
    callback,
    Output,
    Input,
    State,
    register_page,
    no_update,
    html,
    clientside_callback,
)
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import pandas as pd
from config.signals import get_signal_label, get_signal_unit
from services.backend_service import get_metadata, get_tabular

register_page(
    __name__,
    path="/sherlock/data-exploration/polarization-curves",
    title="HOLMES - Sherlock - Polcurve Viewer",
)

USAGE_BLOCKQUOTE_TEXT = [
    "Data Load: Data will load only after selecting Order IDs or Sample Names",
    "Find Test Rigs: Use the Testrig ID field to search or filter specific test rigs.",
    "Refine Selection: Adjust the sliders for anode inlet temperature / cathode outlet pressure, and use the direction control to filter by rising, falling, or both curve types.",
    "Export: Click Download CSV to save your filtered dataset",
]

POLCURVE_TEMP_SIGNAL = "t_an_in"
POLCURVE_PRESSURE_SIGNAL = "p_cat_out"
POLCURVE_X_SIGNAL = "j"
POLCURVE_Y_SIGNAL = "u_cell_avg"
def _get_slider_config(df, col):
    if col not in df.columns:
        return 0, 1, [0, 1], {0: "0", 1: "1"}
    numeric = pd.to_numeric(df[col], errors="coerce").dropna()
    if numeric.empty:
        return 0, 1, [0, 1], {0: "0", 1: "1"}

    min_v = round(float(numeric.min()), 2)
    max_v = round(float(numeric.max()), 2)
    if min_v == max_v:
        return min_v, max_v, [min_v, max_v], {min_v: f"{min_v:.2f}"}

    return (
        min_v,
        max_v,
        [min_v, max_v],
        {min_v: f"{min_v:.2f}", max_v: f"{max_v:.2f}"},
    )


def _apply_local_polcurve_filters(df, tSp_range, pCtSp_range, filter_type):
    temp_col = POLCURVE_TEMP_SIGNAL if POLCURVE_TEMP_SIGNAL in df.columns else None
    pressure_col = (
        POLCURVE_PRESSURE_SIGNAL if POLCURVE_PRESSURE_SIGNAL in df.columns else None
    )

    if temp_col and tSp_range and len(tSp_range) == 2:
        t_numeric = pd.to_numeric(df[temp_col], errors="coerce")
        df = df[(t_numeric >= tSp_range[0]) & (t_numeric <= tSp_range[1])]
    if pressure_col and pCtSp_range and len(pCtSp_range) == 2:
        p_numeric = pd.to_numeric(df[pressure_col], errors="coerce")
        df = df[(p_numeric >= pCtSp_range[0]) & (p_numeric <= pCtSp_range[1])]
    if "is_rising" in df.columns:
        if filter_type == "rising":
            df = df[df["is_rising"] == True]
        elif filter_type == "falling":
            df = df[df["is_rising"] == False]
    return df


def _as_list(value):
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _has_selection(value):
    return value not in (None, "", [], (), set())


def _resolve_testrig_column(df):
    if "testrig_id" in df.columns:
        return "testrig_id"
    if "testrig_label" in df.columns:
        return "testrig_label"
    return None


def _apply_polcurve_metadata_filters(
    df, order_id=None, testrig_id=None, sample_name=None, exclude=None
):
    filtered = df

    if exclude != "order_id" and _has_selection(order_id) and "order_id" in filtered.columns:
        selected_orders = _as_list(order_id)
        filtered = filtered[filtered["order_id"].isin(selected_orders)]

    if exclude != "testrig_id" and _has_selection(testrig_id):
        testrig_column = _resolve_testrig_column(filtered)
        if testrig_column:
            selected_testrigs = {str(value) for value in _as_list(testrig_id)}
            filtered = filtered[
                filtered[testrig_column].astype(str).isin(selected_testrigs)
            ]

    if (
        exclude != "sample_name"
        and _has_selection(sample_name)
        and "sample_name" in filtered.columns
    ):
        selected_samples = _as_list(sample_name)
        filtered = filtered[filtered["sample_name"].isin(selected_samples)]

    return filtered


def _to_options(values):
    return [{"label": str(value), "value": value} for value in values]


def _empty_polcurve_figure(theme, message="No plot available for selected data."):
    import plotly.graph_objects as go

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


# ========== LAYOUT ==========

layout = dmc.Container(
    size="xl",
    py="md",
    style={
        "height": "calc(100dvh - var(--app-shell-header-offset, 0rem))",
        "display": "flex",
        "flexDirection": "column",
        "minHeight": 0,
    },
    children=[
        dmc.Stack(
            gap="md",
            style={"flex":  "1 1 0", "minHeight": 0},
            children=[
                # Title and info
                dmc.Stack(
                    gap=2,
                    children=[
                        dmc.Group(
                            gap="xs",
                            align="center",
                            children=[
                                dmc.Title("Polarization Curve Viewer", order=2),
                                dmc.ActionIcon(
                                    DashIconify(
                                        icon="material-symbols:info-outline", width=20
                                    ),
                                    id="polcurve-usage-toggle",
                                    variant="subtle",
                                    color="blue",
                                    size="md",
                                    radius="xl",
                                ),
                            ],
                        ),
                        dmc.Text(
                            "Explore polarization curve data from Sherlock.", c="dimmed"
                        ),
                        dmc.Collapse(
                            dmc.Blockquote(
                                dmc.List(
                                    withPadding=False,
                                    children=[
                                        dmc.ListItem(item)
                                        for item in USAGE_BLOCKQUOTE_TEXT
                                    ],
                                ),
                                color="blue",
                            ),
                            id="polcurve-usage-collapse",
                        ),
                    ],
                ),
                dmc.Paper(
                    withBorder=True,
                    p="md",
                    radius="md",
                    style={
                        "flex": "1 1 0",
                        "minHeight": 0,
                        "display": "flex",
                        "flexDirection": "column",
                        "overflow": "hidden",
                    },
                    children=[
                        dmc.Group(
                            gap="md",
                            align="flex-end",
                            style={"flexWrap": "nowrap", "overflowX": "auto"},
                            children=[
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="polcurve-order-id-filter",
                                        multi=True,
                                        placeholder="Order ID",
                                        style={"width": "100%"},
                                    ),
                                    label="Order ID",
                                    htmlFor="polcurve-order-id-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "180px"},
                                ),
                                
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="polcurve-sample-name-filter",
                                        multi=True,
                                        placeholder="Sample Name",
                                        style={"width": "100%"},
                                    ),
                                    label="Sample Name",
                                    htmlFor="polcurve-sample-name-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "180px"},
                                ),
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="polcurve-testrig-id-filter",
                                        multi=True,
                                        placeholder="Testrig ID",
                                        style={"width": "100%"},
                                    ),
                                    label="Testrig ID",
                                    htmlFor="polcurve-testrig-id-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "180px"},
                                ),
                                dmc.Button(
                                    "Clear",
                                    id="polcurve-clear-filters-btn",
                                    variant="light",
                                    size="sm",
                                    style={
                                        "flex": "0 0 auto",
                                        "whiteSpace": "nowrap",
                                        "alignSelf": "flex-end",
                                    },
                                ),
                                dmc.Button(
                                    [
                                        html.I(
                                            className="bi bi-download",
                                            style={
                                                "marginRight": "10px",
                                                "fontSize": "1.1em",
                                            },
                                        ),
                                        "Download CSV",
                                    ],
                                    id="polcurve-download-btn",
                                    n_clicks=0,
                                    className="download-btn",
                                    style={
                                        "flex": "0 0 auto",
                                        "whiteSpace": "nowrap",
                                        "alignSelf": "flex-end",
                                    },
                                ),
                            ],
                        ),
                        dcc.Download(id="polcurve-download-csv"),
                        dmc.Space(h="sm"),
                        dmc.Text(
                            id="polcurve-empty-message",
                            c="red",
                            fw=600,
                            style={"display": "none"},
                        ),
                        dmc.Divider(size="xs", my="sm"),
                        dmc.Box(
                            style={
                                "display": "flex",
                                "flexDirection": "column",
                                "flex": "1 1 0",
                                "minHeight": 0,
                            },
                            children=[
                                dmc.Box(
                                    mb="sm",
                                    style={
                                        "display": "grid",
                                        "gridTemplateColumns": "minmax(260px, 1fr) minmax(260px, 1fr) minmax(80px, 100px)",
                                        "gap": "16px",
                                        "alignItems": "stretch",
                                        "width": "100%",
                                    },
                                    children=[
                                        dmc.Stack(
                                            gap=4,
                                            style={
                                                "width": "100%",
                                            },
                                            children=[
                                                dmc.Text(
                                                    "Anode Inlet Temperature",
                                                    fw=500,
                                                    size="sm",
                                                ),
                                                dmc.RangeSlider(
                                                    id="polcurve-temp-set-filter",
                                                    min=0,
                                                    max=1,
                                                    value=[0, 1],
                                                    step=0.01,
                                                    minRange=0,
                                                    marks=[],
                                                    thumbSize=16,
                                                    size="sm",
                                                ),
                                                html.Div(
                                                    style={},
                                                    children=dmc.BubbleChart(
                                                        id="polcurve-temp-distribution-chart",
                                                        h=70,
                                                        data=[],
                                                        range=[10, 30],
                                                        color="blue.6",
                                                        dataKey={
                                                            "x": "bucket",
                                                            "y": "row",
                                                            "z": "count",
                                                        },
                                                        yAxisProps={"hide": True},
                                                        xAxisProps={
                                                            "interval": "preserveStartEnd"
                                                        },
                                                        style={
                                                            "width": "100%",
                                                            "overflow": "hidden",
                                                        },
                                                        withTooltip=True,
                                                    ),
                                                ),
                                            ],
                                        ),
                                        dmc.Stack(
                                            gap=4,
                                            style={
                                                "width": "100%",
                                            },
                                            children=[
                                                dmc.Text(
                                                    "Cathode Outlet Pressure",
                                                    fw=500,
                                                    size="sm",
                                                ),
                                                dmc.RangeSlider(
                                                    id="polcurve-pressure-set-filter",
                                                    min=0,
                                                    max=1,
                                                    value=[0, 1],
                                                    step=0.01,
                                                    minRange=0,
                                                    marks=[],
                                                    thumbSize=16,
                                                    size="sm",
                                                ),
                                                html.Div(
                                                    style={},
                                                    children=dmc.BubbleChart(
                                                        id="polcurve-pressure-distribution-chart",
                                                        h=70,
                                                        data=[],
                                                        range=[10, 30],
                                                        color="teal.6",
                                                        dataKey={
                                                            "x": "bucket",
                                                            "y": "row",
                                                            "z": "count",
                                                        },
                                                        yAxisProps={"hide": True},
                                                        xAxisProps={
                                                            "interval": "preserveStartEnd"
                                                        },
                                                        style={
                                                            "width": "100%",
                                                            "overflow": "hidden",
                                                        },
                                                        withTooltip=True,
                                                    ),
                                                ),
                                            ],
                                        ),
                                        dmc.Stack(
                                            gap=4,
                                            style={
                                                "width": "100%",
                                                "height": "100%",
                                            },
                                            children=[
                                                dmc.Text(
                                                    "Direction", fw=500, size="sm"
                                                ),
                                                dmc.SegmentedControl(
                                                    id="polcurve-is-rising-filter",
                                                    data=["Both", "Rising", "Falling"],
                                                    value="Both",
                                                    orientation="vertical",
                                                    fullWidth=True,
                                                    style={"flex": 1},
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                dmc.Text(
                                    id="polcurve-plot-message",
                                    c="red",
                                    fw=600,
                                    style={"textAlign": "center"},
                                ),
                                dcc.Graph(
                                    id="polcurve-plot",
                                    config={"responsive": True},
                                    style={"height": "100%", "flex": 1, "minHeight": 0},
                                ),
                            ],
                        ),
                    ],
                ),
                dcc.Store(id="polcurve-metadata-store"),
                dcc.Store(id="polcurve-data-store"),
                dcc.Store(id="polcurve-usage-open", data=False),
                dcc.Store(id="polcurve-theme-store"),
                html.Div(id="polcurve-theme-dummy", style={"display": "none"}),
            ],
        )
    ],
)

# ========== CLEAR FILTERS ==========


@callback(
    Output("polcurve-order-id-filter", "value", allow_duplicate=True),
    Output("polcurve-sample-name-filter", "value", allow_duplicate=True),
    Output("polcurve-testrig-id-filter", "value", allow_duplicate=True),
    Output("polcurve-is-rising-filter", "value", allow_duplicate=True),
    Input("polcurve-clear-filters-btn", "n_clicks"),
    prevent_initial_call=True,
)
def clear_polcurve_filters(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    return [], [], [], "Both"


# ========== INFO PANEL COLLAPSE ==========


@callback(
    Output("polcurve-usage-open", "data"),
    Input("polcurve-usage-toggle", "n_clicks"),
    State("polcurve-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage_panel(n, open_state):
    if n:
        return not open_state
    return open_state


@callback(
    Output("polcurve-usage-collapse", "opened"),
    Input("polcurve-usage-open", "data"),
)
def set_usage_panel_open(open_state):
    return open_state


# ========== LAZY LOAD METADATA FOR FILTERS ==========


@callback(
    Output("polcurve-metadata-store", "data"),
    Input("polcurve-order-id-filter", "id"),  # triggers on page load
)
def load_polcurve_metadata(_):
    meta = get_metadata("sherlock", "polcurve")
    # meta is a list of dicts, each dict is a row with all columns
    df = pd.DataFrame(meta)
    return df.to_dict("list") if not df.empty else {}


@callback(
    Output("polcurve-order-id-filter", "options"),
    Output("polcurve-order-id-filter", "value"),
    Output("polcurve-testrig-id-filter", "options"),
    Output("polcurve-testrig-id-filter", "value"),
    Output("polcurve-sample-name-filter", "options"),
    Output("polcurve-sample-name-filter", "value"),
    Input("polcurve-metadata-store", "data"),
    Input("polcurve-order-id-filter", "value"),
    Input("polcurve-sample-name-filter", "value"),
    Input("polcurve-testrig-id-filter", "value"),
)
def sync_polcurve_filters(meta, current_order_id, current_sample_name, current_testrig_id):
    if not meta:
        return [], [], [], [], [], []

    df = pd.DataFrame(meta)

    order_df = _apply_polcurve_metadata_filters(
        df,
        testrig_id=current_testrig_id,
        sample_name=current_sample_name,
        exclude="order_id",
    )
    order_values = (
        sorted(order_df["order_id"].dropna().unique().tolist(), reverse=True)
        if "order_id" in order_df.columns
        else []
    )

    selected_order = [
        value for value in _as_list(current_order_id) if value in order_values
    ]
    if not selected_order and current_order_id is None and current_sample_name is None and current_testrig_id is None:
        selected_order = [order_values[0]] if order_values else []

    testrig_df = _apply_polcurve_metadata_filters(
        df,
        order_id=selected_order,
        sample_name=current_sample_name,
        exclude="testrig_id",
    )
    testrig_column = _resolve_testrig_column(testrig_df)
    testrig_values = (
        sorted(testrig_df[testrig_column].dropna().unique().tolist(), key=str)
        if testrig_column
        else []
    )
    selected_testrig = [
        value
        for value in _as_list(current_testrig_id)
        if str(value) in {str(option) for option in testrig_values}
    ]

    sample_df = _apply_polcurve_metadata_filters(
        df,
        order_id=selected_order,
        testrig_id=selected_testrig,
        exclude="sample_name",
    )
    sample_values = (
        sorted(sample_df["sample_name"].dropna().unique().tolist(), key=str)
        if "sample_name" in sample_df.columns
        else []
    )
    selected_sample = [
        value for value in _as_list(current_sample_name) if value in sample_values
    ]

    return (
        _to_options(order_values),
        selected_order,
        _to_options(testrig_values),
        selected_testrig,
        _to_options(sample_values),
        selected_sample,
    )


# ========== LAZY LOAD DATA WHEN FILTERS SELECTED ==========


@callback(
    Output("polcurve-data-store", "data"),
    Output("polcurve-empty-message", "children"),
    Output("polcurve-empty-message", "style"),
    Input("polcurve-order-id-filter", "value"),
    Input("polcurve-sample-name-filter", "value"),
)
def fetch_polcurve_data(order_id, sample_name):
    filters = {}
    if order_id:
        filters["order_id"] = order_id
    if sample_name:
        filters["sample_name"] = sample_name
    if not filters:
        return (
            [],
            "Select at least one order ID or sample name to load data.",
            {"display": "block"},
        )
    df = get_tabular("sherlock", "polcurve", filters=filters)
    if df.empty:
        return [], "No data found for selected filters.", {"display": "block"}
    else:
        df["event_short_id"] = df.apply(
            lambda row: f"{row['sample_name']}_{row['order_id']}_{str(row['event_id']).split('_')[-1]}",
            axis=1,
        )

    return df.to_dict("records"), "", {"display": "none"}


# ========== DATA-DRIVEN LOCAL FILTER CONFIG ==========


@callback(
    Output("polcurve-temp-set-filter", "min"),
    Output("polcurve-temp-set-filter", "max"),
    Output("polcurve-temp-set-filter", "value"),
    Output("polcurve-pressure-set-filter", "min"),
    Output("polcurve-pressure-set-filter", "max"),
    Output("polcurve-pressure-set-filter", "value"),
    Output("polcurve-temp-distribution-chart", "data"),
    Output("polcurve-temp-distribution-chart", "range"),
    Output("polcurve-pressure-distribution-chart", "data"),
    Output("polcurve-pressure-distribution-chart", "range"),
    Input("polcurve-data-store", "data"),
    Input("polcurve-is-rising-filter", "value"),  # <-- add this
)
def populate_data_driven_filter_options(data, is_rising):
    import numpy as np

    if not data:
        return 0, 1, [0, 1], 0, 1, [0, 1], [], [10, 30], [], [10, 30]
    df = pd.DataFrame(data)

    def _build_bubble_distribution(series, bins=10):
        numeric = pd.to_numeric(series, errors="coerce").dropna()
        if numeric.empty:
            return [], [10, 30]

        counts, bin_edges = np.histogram(numeric, bins=bins)
        bubble_data = []
        for i in range(len(counts)):
            count = int(counts[i])
            if count <= 0:
                continue
            center = round(float((bin_edges[i] + bin_edges[i + 1]) / 2), 2)
            bubble_data.append({"bucket": f"{center:.2f}", "row": 1, "count": count})

        if not bubble_data:
            return [], [10, 30]

        max_count = max(item["count"] for item in bubble_data)
        return bubble_data, [10, max(18, min(40, 10 + max_count * 2))]

    # Apply direction filter
    df = _apply_local_polcurve_filters(df, None, None, (is_rising or "both").lower())
    temp_col = POLCURVE_TEMP_SIGNAL if POLCURVE_TEMP_SIGNAL in df.columns else None
    pressure_col = (
        POLCURVE_PRESSURE_SIGNAL if POLCURVE_PRESSURE_SIGNAL in df.columns else None
    )
    t_min, t_max, t_value, _ = _get_slider_config(df, temp_col or "")
    p_min, p_max, p_value, _ = _get_slider_config(df, pressure_col or "")

    temp_bubble_data, temp_bubble_range = _build_bubble_distribution(df.get(temp_col))
    pressure_bubble_data, pressure_bubble_range = _build_bubble_distribution(
        df.get(pressure_col)
    )

    return (
        t_min,
        t_max,
        t_value,
        p_min,
        p_max,
        p_value,
        temp_bubble_data,
        temp_bubble_range,
        pressure_bubble_data,
        pressure_bubble_range,
    )


# ========== THEME SYNC CALLBACKS ==========

# Sync AG Grid theme with Mantine color scheme
clientside_callback(
    """
    (theme) => {
       document.documentElement.setAttribute('data-ag-theme-mode', theme === 'dark' ? 'dark' : 'light');
       return window.dash_clientside.no_update;
    }
    """,
    Output("polcurve-theme-dummy", "children"),
    Input("theme-store", "data"),
)


# Forward theme-store to polcurve-theme-store for server-side callbacks
@callback(
    Output("polcurve-theme-store", "data"),
    Input("theme-store", "data"),
    prevent_initial_call=False,
)
def sync_theme_store(theme):
    return theme


# ========== PLOT CALLBACK ==========


@callback(
    Output("polcurve-plot", "figure"),
    Output("polcurve-plot-message", "children"),
    Input("polcurve-data-store", "data"),
    Input("polcurve-theme-store", "data"),
    Input("polcurve-temp-set-filter", "value"),
    Input("polcurve-pressure-set-filter", "value"),
    Input("polcurve-is-rising-filter", "value"),
)
def update_polcurve_plot(data, theme, tSp, pCtSp, is_rising):
    import plotly.express as px

    if not data:
        return _empty_polcurve_figure(theme), "No plot available for selected data."
    df = pd.DataFrame(data)
    df = _apply_local_polcurve_filters(df, tSp, pCtSp, (is_rising or "both").lower())
    x_col = POLCURVE_X_SIGNAL if POLCURVE_X_SIGNAL in df.columns else None
    y_col = POLCURVE_Y_SIGNAL if POLCURVE_Y_SIGNAL in df.columns else None
    if x_col and y_col:
        color_col = "event_short_id" if "event_short_id" in df else None
        plot_df = df.dropna(subset=[y_col, x_col])
        if plot_df.empty:
            return _empty_polcurve_figure(theme), "No plot available for selected data."
        plotly_template = "plotly_dark" if theme == "dark" else "plotly"
        fig = px.line(
            (
                plot_df.sort_values([color_col, x_col])
                if color_col
                else plot_df.sort_values(x_col)
            ),
            x=x_col,
            y=y_col,
            color=color_col,
            labels={
                x_col: f"{get_signal_label(POLCURVE_X_SIGNAL)} [{get_signal_unit(POLCURVE_X_SIGNAL)}]",
                y_col: f"{get_signal_label(POLCURVE_Y_SIGNAL)} [{get_signal_unit(POLCURVE_Y_SIGNAL)}]",
            },
            template=plotly_template,
        )
        return fig, ""
    return _empty_polcurve_figure(theme), "No plot available for selected data."


# ========== DOWNLOAD CALLBACK ==========


@callback(
    Output("polcurve-download-csv", "data"),
    Input("polcurve-download-btn", "n_clicks"),
    State("polcurve-data-store", "data"),
    prevent_initial_call=True,
)
def download_polcurve_table(n_clicks, data):
    if not data:
        return no_update
    df = pd.DataFrame(data)
    return dcc.send_data_frame(df.to_csv, "polcurve_data.csv", index=False)
