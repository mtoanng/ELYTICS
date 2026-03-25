from dash import dcc, callback, Output, Input, State, register_page, no_update,html,clientside_callback
import dash_mantine_components as dmc
import dash_ag_grid as dag
from dash_iconify import DashIconify
import pandas as pd
from services.backend_service import get_metadata, get_tabular

register_page(
    __name__,
    path="/sherlock/data-exploration/polarization-curves",
    title="HOLMES - Sherlock - Polcurve Viewer",
)

USAGE_BLOCKQUOTE_TEXT = [
    "This page allows you to explore polarization curve data.",
    "Select at least one filter to load and plot data.",
    "Download the table as CSV using the Download CSV button below the filters.",
]

# ========== LAYOUT ==========

layout = dmc.Container(
    size="xl",
    py="md",
    children=[
        dmc.Stack(
            gap="md",
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
                # Filters and download
                dmc.Paper(
                    withBorder=True,
                    p="md",
                    radius="md",
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
                            ],
                        ),
                        dmc.Group(
                            gap="md",
                            align="flex-end",
                            mt="xs",
                            style={"flexWrap": "nowrap", "overflowX": "auto"},
                            children=[
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="polcurve-temp-set-filter",
                                        multi=True,
                                        placeholder="Temperature Setpoint",
                                        style={"width": "100%"},
                                    ),
                                    label="Temperature Setpoint",
                                    htmlFor="polcurve-temp-set-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "180px"},
                                ),
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="polcurve-pressure-set-filter",
                                        multi=True,
                                        placeholder="Pressure Setpoint",
                                        style={"width": "100%"},
                                    ),
                                    label="Pressure Setpoint",
                                    htmlFor="polcurve-pressure-set-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "180px"},
                                ),
                                dmc.InputWrapper(
                                    dmc.SegmentedControl(
                                        id="polcurve-is-rising-filter",
                                        data=[
                                            {"label": "Both", "value": "both"},
                                            {"label": "Rising", "value": "rising"},
                                            {"label": "Falling", "value": "falling"},
                                        ],
                                        value="both",
                                        size="sm",
                                        radius="md",
                                        style={"width": "100%", "minWidth": "220px"},
                                    ),
                                    label="is_rising",
                                    htmlFor="polcurve-is-rising-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "180px"},
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
                                dcc.Download(id="polcurve-download-csv"),
                            ],
                        ),
                        dmc.Space(h="sm"),
                        dmc.Text(
                            id="polcurve-empty-message",
                            c="red",
                            fw=600,
                            style={"display": "none"},
                        ),
                    ],
                ),
                # Plot and table
                dmc.SimpleGrid(
                    cols=1,
                    spacing="md",
                    verticalSpacing="md",
                    children=[
                        dmc.Paper(
                            withBorder=True,
                            p="xs",
                            radius="md",
                            children=[
                                dmc.Text(id="polcurve-view-label", fw=600, size="sm"),
                                dcc.Graph(
                                    id="polcurve-plot",
                                    config={"responsive": True},
                                    style={"height": 500},
                                ),
                            ],
                        ),
                        dmc.Paper(
                            withBorder=True,
                            p="xs",
                            radius="md",
                            children=[
                                dmc.Text("Table", fw=600, size="sm"),
                                dcc.Store(id="polcurve-table-store"),
                                dcc.Loading(
                                    id="polcurve-table-loading",
                                    type="default",
                                    children=[
                                        dag.AgGrid(
                                            id="polcurve-table",
                                            columnDefs=[],  # Will be set by callback
                                            rowData=[],
                                            defaultColDef={
                                                "resizable": True,
                                                "sortable": True,
                                                "filter": True,
                                                "minWidth": 110,
                                            },
                                            dashGridOptions={
                                                "pagination": True,
                                                "paginationPageSize": 20,
                                                "animateRows": True,
                                                "floatingFilter": True,
                                                "groupDisplayType": "multipleColumns",
                                            },
                                            style={"height": 350, "width": "100%"},
                                        )
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
                dcc.Store(id="polcurve-metadata-store"),
                dcc.Store(id="polcurve-data-store"),
                dcc.Store(id="polcurve-usage-open", data=True),
                dcc.Store(id="polcurve-theme-store"),
                html.Div(id="polcurve-theme-dummy"),
            ],
        )
    ],
)

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
    Output("polcurve-sample-name-filter", "options"),
    Output("polcurve-testrig-id-filter", "options"),
    Input("polcurve-metadata-store", "data"),
    Input("polcurve-order-id-filter", "value"),
)
def populate_cascading_filter_options(meta, order_id):
    if not meta:
        return [], [], []
    df = pd.DataFrame(meta)
    # Order ID options (always all)
    order_id_options = (
        [
            {"label": str(oid), "value": oid}
            for oid in sorted(df["order_id"].dropna().unique(), reverse=True)
        ]
        if "order_id" in df
        else []
    )
    # Filter sample names and testrig ids by selected order_id(s)
    dff = df.copy()
    if order_id:
        dff = dff[dff["order_id"].isin(order_id)]
    sample_name_options = (
        [
            {"label": str(s), "value": s}
            for s in sorted(dff["sample_name"].dropna().unique())
        ]
        if "sample_name" in dff
        else []
    )
    testrig_id_options = (
        [
            {"label": str(t), "value": t}
            for t in sorted(dff["testrig_id"].dropna().unique())
        ]
        if "testrig_id" in dff
        else []
    )
    return (
        order_id_options,
        sample_name_options,
        testrig_id_options,
    )


# ========== LAZY LOAD DATA WHEN FILTERS SELECTED ==========


@callback(
    Output("polcurve-data-store", "data"),
    Output("polcurve-empty-message", "children"),
    Output("polcurve-empty-message", "style"),
    Input("polcurve-order-id-filter", "value"),
    Input("polcurve-sample-name-filter", "value"),
    Input("polcurve-testrig-id-filter", "value"),
)
def fetch_polcurve_data(order_id, sample_name, testrig_id):
    filters = {}
    if order_id:
        filters["order_id"] = order_id
    if sample_name:
        filters["sample_name"] = sample_name
    if testrig_id:
        filters["testrig_id"] = testrig_id
    if not filters:
        return [], "Select at least one filter to load data.", {"display": "block"}
    df = get_tabular("sherlock", "polcurve", filters=filters)
    if df.empty:
        return [], "No data found for selected filters.", {"display": "block"}
    return df.to_dict("records"), "", {"display": "none"}


# ========== TABLE RENDERING ==========


# ========== DATA-DRIVEN FILTER OPTIONS (tSp, is_rising) ==========


@callback(
    Output("polcurve-temp-set-filter", "options"),
    Output("polcurve-pressure-set-filter", "options"),
    Input("polcurve-data-store", "data"),
)
def populate_data_driven_filter_options(data):
    if not data:
        return [], []
    df = pd.DataFrame(data)
    tSp_options = (
        [
            {"label": str(int(t)) if float(t).is_integer() else str(t), "value": t}
            for t in sorted(df["tSp"].dropna().unique())
        ]
        if "tSp" in df.columns
        else []
    )
    pCtSp_options = (
        [
            {"label": str(int(p)) if float(p).is_integer() else str(p), "value": p}
            for p in sorted(df["pCtSp"].dropna().unique())
        ]
        if "pCtSp" in df.columns
        else []
    )
    return tSp_options, pCtSp_options


# ========== TABLE RENDERING ==========


@callback(
    Output("polcurve-table", "columnDefs"),
    Output("polcurve-table", "rowData"),
    Input("polcurve-data-store", "data"),
    Input("polcurve-temp-set-filter", "value"),
    Input("polcurve-pressure-set-filter", "value"),
    Input("polcurve-is-rising-filter", "value"),
)
def render_polcurve_table(data, tSp, pCtSp, is_rising):
    if not data:
        return [], []
    df = pd.DataFrame(data)
    if tSp:
        df = df[df["tSp"].isin(tSp)]
    if pCtSp:
        df = df[df["pCtSp"].isin(pCtSp)]
    if "is_rising" in df.columns:
        if is_rising == "rising":
            df = df[df["is_rising"] == True]
        elif is_rising == "falling":
            df = df[df["is_rising"] == False]
    columns = df.columns.tolist()
    columnDefs = []
    for col in columns:
        col_type = "numeric" if pd.api.types.is_numeric_dtype(df[col]) else "text"
        columnDefs.append({"headerName": col, "field": col, "type": col_type})
    return columnDefs, df.to_dict("records")

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
    Output("polcurve-view-label", "children"),
    Input("polcurve-data-store", "data"),
    Input("polcurve-theme-store", "data"),
    Input("polcurve-temp-set-filter", "value"),
    Input("polcurve-pressure-set-filter", "value"),
    Input("polcurve-is-rising-filter", "value"),
)
def update_polcurve_plot(data, theme, tSp, pCtSp, is_rising):
    import plotly.express as px

    if not data:
        return {}, ""
    df = pd.DataFrame(data)
    if tSp:
        df = df[df["tSp"].isin(tSp)]
    if pCtSp:
        df = df[df["pCtSp"].isin(pCtSp)]
    if "is_rising" in df.columns:
        if is_rising == "rising":
            df = df[df["is_rising"] == True]
        elif is_rising == "falling":
            df = df[df["is_rising"] == False]
    # Plot uCell vs jStck for each event_id if present
    if "uCell" in df and "jStck" in df:
        color_col = "event_id" if "event_id" in df else None
        # Remove rows with missing values in either column
        plot_df = df.dropna(subset=["uCell", "jStck"])
        if plot_df.empty:
            return {}, "No plot available for selected data."
        plotly_template = "plotly_dark" if theme == "dark" else "plotly"
        fig = px.line(
            plot_df.sort_values([color_col, "jStck"]) if color_col else plot_df.sort_values("jStck"),
            x="jStck",
            y="uCell",
            color=color_col,
            template=plotly_template,
        )
        label = "Polarization Curve" + (" by event_id" if color_col else "")
        return fig, label
    return {}, "No plot available for selected data."


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
