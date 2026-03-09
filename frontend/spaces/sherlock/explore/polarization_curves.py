from dash import html, dcc, callback, Output, Input, State, register_page, no_update
import dash_ag_grid as dag
import pandas as pd
import plotly.graph_objs as go

from services.backend_service import get_table_as_df

register_page(
    __name__,
    path="/sherlock/data-exploration/polarization-curves",
    title="HOLMES - Sherlock - Polcurve Viewer"
)

USAGE_TOOLTIP_TEXT = (
    "This page allows you to explore polarization curve data.\n\n"
    "How to use this page:\n\n"
    "• Use the filters on the left to narrow down the data.\n"
    "• Download the table as CSV using the Download CSV button below the filters."
)

def polcurve_view_layout():
    return html.Div([
        html.Div([
            html.H2("Polarization Curve Viewer"),
            html.Span(
                "ℹ️",
                title=USAGE_TOOLTIP_TEXT,
                style={
                    "cursor": "help",
                    "marginLeft": "6px",
                    "fontSize": "16px",
                    "opacity": 0.75,
                },
            ),
        ], style={
            "display": "flex",
            "alignItems": "center",
            "gap": "4px",
            "marginBottom": "12px",
        }),

        dcc.Store(id="polcurve-data-store"),

        # Wrap all main content in a single Loading spinner
        dcc.Loading(
            id="polcurve-main-loading",
            type="default",
            color="#2d98da",
            fullscreen=False,
            children=html.Div(id="polcurve-main-content", children="") # empty div to be populated after data load to allow for spinner to show

        ),
    ])

layout = polcurve_view_layout

# --- Load all polcurve data on page load ---
@callback(
    Output("polcurve-data-store", "data"),
    Input("polcurve-main-content", "id"),
)
def load_polcurve_data(_):
    df = get_table_as_df('sherlock', 'polcurve_view')
    if df.empty:
        return []
    num_cols = df.select_dtypes(include="number").columns
    df[num_cols] = df[num_cols].round(3)
    return df.to_dict("records")

# --- Render main content only after data is loaded ---
@callback(
    Output("polcurve-main-content", "children"),
    Input("polcurve-data-store", "data"),
)
def render_main_content(data):
    if not data:
        return ""
    df = pd.DataFrame(data)
    # Filter options from full data
    order_id_options = [
        {"label": str(oid), "value": oid}
        for oid in sorted(df["order_id"].dropna().unique(), reverse=True)
    ]
    sample_name_options = [
        {"label": str(s), "value": s}
        for s in sorted(df["sample_name"].dropna().unique())
    ]
    testrig_id_options = [
        {"label": str(t), "value": t}
        for t in sorted(df["testrig_id"].dropna().unique())
    ]
    tSp_options = [
        {"label": str(int(t)) if pd.notnull(t) else "", "value": t}
        for t in sorted(df["tSp"].dropna().unique())
    ]
    is_rising_options = [
        {"label": str(r), "value": r}
        for r in sorted(df["is_rising"].dropna().unique())
    ]
    return html.Div([
        html.Div([
            html.Label("Order ID:"),
            dcc.Dropdown(
                id="polcurve-order-id-filter",
                options=order_id_options,
                multi=True,
                searchable=True,
                clearable=True,
                style={"width": "180px"}
            ),
            html.Label("Sample Name:"),
            dcc.Dropdown(
                id="polcurve-sample-name-filter",
                options=sample_name_options,
                multi=True,
                searchable=True,
                clearable=True,
                style={"width": "180px"}
            ),
            html.Label("Testrig ID:"),
            dcc.Dropdown(
                id="polcurve-testrig-id-filter",
                options=testrig_id_options,
                multi=True,
                searchable=True,
                clearable=True,
                style={"width": "180px"}
            ),
            html.Label("Temperature Setpoint:"),
            dcc.Dropdown(
                id="polcurve-temp-set-filter",
                options=tSp_options,
                multi=True,
                searchable=True,
                clearable=True,
                style={"width": "180px"}
            ),
            html.Label("is_rising:"),
            dcc.Dropdown(
                id="polcurve-is-rising-filter",
                options=is_rising_options,
                multi=False,
                searchable=True,
                clearable=True,
                style={"width": "180px"}
            ),
            html.Br(),
            html.Button([
                html.I(className="bi bi-download", style={"marginRight": "8px", "fontSize": "1.2em"}),
                "Download CSV"
            ], id="polcurve-download-btn", n_clicks=0, className="download-btn", style={
                "marginTop": "4px",
                "display": "flex",
                "alignItems": "center",
                "marginBottom": "30px",
                "borderRadius": "6px",
                "padding": "6px 12px",
                "fontWeight": "600",
                "fontSize": "14px",
                "cursor": "pointer"
            }),
            dcc.Download(id="polcurve-download-csv"),
        ], style={"width": "200px", "display": "inline-block", "verticalAlign": "top", "marginRight": "20px"}),

        html.Div([
            html.Div(id="polcurve-empty-message", style={"color": "#c0392b", "fontWeight": "bold", "marginBottom": "1em", "fontSize": "1.1em", "display": "none"}, role="alert"),
            html.Div(
                id="polcurve-count-boxes",
                style={
                    "display": "flex",
                    "justifyContent": "center",
                    "gap": "32px",
                    "marginBottom": "6px",
                }
            ),
            html.Div(id="polcurve-view-label", style={"fontWeight": "bold", "marginBottom": "0.5em", "fontSize": "1em"}),
            dcc.Graph(id="polcurve-plot", style={"height": "35vh"}),
            dag.AgGrid(
                id="polcurve-table",
                columnDefs=[],
                rowData=[],
                defaultColDef={"resizable": True, "sortable": True, "filter": True, "minWidth": 60, "flex": 1, "wrapText": False},
                style={"height": "35vh", "width": "100%", "fontSize": "12px"},
                dashGridOptions={"pagination": True, "paginationPageSize": 14, "domLayout": "normal"},
            )
        ], style={"display": "inline-block", "width": "calc(100% - 240px)"})
    ], style={"display": "flex", "flexDirection": "row"})

# --- Update table, filter options, and empty message based on current selections ---
@callback(
    Output("polcurve-table", "rowData"),
    Output("polcurve-table", "columnDefs"),
    Output("polcurve-empty-message", "children"),
    Output("polcurve-empty-message", "style"),
    Output("polcurve-order-id-filter", "options"),
    Output("polcurve-sample-name-filter", "options"),
    Output("polcurve-testrig-id-filter", "options"),
    Output("polcurve-temp-set-filter", "options"),
    Output("polcurve-is-rising-filter", "options"),
    Input("polcurve-order-id-filter", "value"),
    Input("polcurve-sample-name-filter", "value"),
    Input("polcurve-testrig-id-filter", "value"),
    Input("polcurve-temp-set-filter", "value"),
    Input("polcurve-is-rising-filter", "value"),
    State("polcurve-data-store", "data"),
)
def update_polcurve_table_and_filters(order_id, sample_name, testrig_id, tSp, is_rising, data):
    if not data:
        return [], [], "⚠️ No data available.", {"display": "block"}, [], [], [], [], []
    df = pd.DataFrame(data)
    # Filter options always from full data
    order_id_options = [
        {"label": str(oid), "value": oid}
        for oid in sorted(df["order_id"].dropna().unique(), reverse=True)
    ]
    sample_name_options = [
        {"label": str(s), "value": s}
        for s in sorted(df["sample_name"].dropna().unique())
    ]
    testrig_id_options = [
        {"label": str(t), "value": t}
        for t in sorted(df["testrig_id"].dropna().unique())
    ]
    tSp_options = [
        {"label": str(int(t)) if pd.notnull(t) else "", "value": t}
        for t in sorted(df["tSp"].dropna().unique())
    ]
    is_rising_options = [
        {"label": str(r), "value": r}
        for r in sorted(df["is_rising"].dropna().unique())
    ]
    # Only filter if at least one filter is set
    filters = [order_id, sample_name, testrig_id, tSp, is_rising]
    if not any(f for f in filters if f):  # No filter set
        return [], [], "ℹ️ Select at least one filter to view data.", {"display": "block"}, order_id_options, sample_name_options, testrig_id_options, tSp_options, is_rising_options
    dff = df.copy()
    if order_id:
        dff = dff[dff["order_id"].isin(order_id)]
    if sample_name:
        dff = dff[dff["sample_name"].isin(sample_name)]
    if testrig_id:
        dff = dff[dff["testrig_id"].isin(testrig_id)]
    if tSp:
        dff = dff[dff["tSp"].isin(tSp)]
    if is_rising is not None and is_rising != "":
        dff = dff[dff["is_rising"] == is_rising]
    if dff.empty:
        return [], [], "⚠️ No data available for selected filters.", {"display": "block"}, order_id_options, sample_name_options, testrig_id_options, tSp_options, is_rising_options
    col_defs = []
    for col in dff.columns:
        if col == "is_rising":
            col_defs.append({
                "headerName": col,
                "field": col,
                "filter": True,
                "sortable": True,
                "resizable": True,
                "minWidth": 60,
                "flex": 1,
                "type": "textColumn",
                "valueFormatter": {"function": "params.value === true ? 'True' : (params.value === false ? 'False' : params.value)"}
            })
        elif pd.api.types.is_numeric_dtype(dff[col]):
            col_defs.append({
                "headerName": col,
                "field": col,
                "filter": True,
                "sortable": True,
                "resizable": True,
                "minWidth": 60,
                "flex": 1,
                "type": "rightAligned",
                "valueFormatter": {"function": "params.value == null ? '' : Number(params.value).toFixed(2)"}
            })
        else:
            col_defs.append({
                "headerName": col,
                "field": col,
                "filter": True,
                "sortable": True,
                "resizable": True,
                "minWidth": 60,
                "flex": 1,
            })
    return dff.to_dict("records"), col_defs, "", {"display": "none"}, order_id_options, sample_name_options, testrig_id_options, tSp_options, is_rising_options

# --- Download callback for polcurve table ---
@callback(
    Output("polcurve-download-csv", "data"),
    Input("polcurve-download-btn", "n_clicks"),
    State("polcurve-table", "rowData"),
    prevent_initial_call=True,
)
def download_polcurve_table(n_clicks, table_data):
    if not table_data:
        return no_update
    df_filtered = pd.DataFrame(table_data)
    return dcc.send_data_frame(df_filtered.to_csv, "polcurve_table.csv", index=False)

# --- Count boxes: show total and filtered number of polcurves ---
@callback(
    Output("polcurve-count-boxes", "children"),
    Input("polcurve-data-store", "data"),
    Input("polcurve-table", "rowData"),
)
def update_polcurve_counts(data, table_data):
    total_count = 0
    filtered_count = 0
    if data:
        df = pd.DataFrame(data)
        total_count = df["event_id"].nunique() if "event_id" in df else 0
    if table_data:
        filtered_count = pd.DataFrame(table_data)["event_id"].nunique()
    box_class = "polcurve-count-box"
    return [
        html.Div([
            html.Div("Total number of polcurves", className="polcurve-count-label"),
            html.Div(f"{total_count}", className="polcurve-count-number"),
        ], className=box_class),
        html.Div([
            html.Div("Filtered number of polcurves", className="polcurve-count-label"),
            html.Div(f"{filtered_count}", className="polcurve-count-number"),
        ], className=box_class),
    ]

# --- Plot callback ---
@callback(
    Output("polcurve-plot", "figure"),
    Output("polcurve-view-label", "children"),
    Input("polcurve-table", "rowData"),
)
def update_polcurve_plot(table_data):
    if not table_data:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_white",
            xaxis_title="jStck",
            yaxis_title="uCell",
            legend_title="event_id",
            margin=dict(l=40, r=20, t=40, b=40)
        )
        return fig, ""
    dff = pd.DataFrame(table_data)
    label = "filtered data"
    if dff.empty:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_white",
            xaxis_title="jStck",
            yaxis_title="uCell",
            legend_title="event_id",
            margin=dict(l=40, r=20, t=40, b=40)
        )
        return fig, label
    x_col = "jStck"
    y_col = "uCell"
    group_cols = ["event_id", "is_rising"]
    fig = go.Figure()
    if not all(col in dff.columns for col in [x_col, y_col] + group_cols):
        fig.update_layout(
            template="plotly_white",
            xaxis_title=x_col,
            yaxis_title=y_col,
            legend_title="event_id",
            margin=dict(l=40, r=20, t=40, b=40)
        )
        return fig, label
    event_ids = sorted(dff["event_id"].dropna().unique())
    for event_id in event_ids:
        sub = dff[dff["event_id"] == event_id]
        if not sub.empty:
            fig.add_trace(go.Scattergl(
                x=sub[x_col],
                y=sub[y_col],
                mode="lines+markers",
                name=f"event {event_id}",
                showlegend=False,
                customdata=sub[["order_id", "event_id", "tSp", "is_rising"]],
                hovertemplate=(
                    "<b>jStck</b>: %{x}<br>"
                    "<b>uCell</b>: %{y}<br>"
                    "<b>Order ID</b>: %{customdata[0]}<br>"
                    "<b>Event ID</b>: %{customdata[1]}<br>"
                    "<b>tSp</b>: %{customdata[2]}<br>"
                    "<b>is_rising</b>: %{customdata[3]}<extra></extra>"
                ),
            ))
    fig.update_layout(
        template="plotly_white",
        xaxis_title=x_col,
        yaxis_title=y_col,
        legend_title="event_id",
        margin=dict(l=40, r=20, t=40, b=40)
    )
    return fig, label