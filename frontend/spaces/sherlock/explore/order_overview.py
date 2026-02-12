from dash import html, dcc, callback, Output, Input, State, register_page, no_update
import dash_ag_grid as dag
import pandas as pd

from services.backend_service import get_table_as_df

register_page(
    __name__,
    path="/sherlock/data-exploration/order-overview",
    title="Order Overview Space"
)

USAGE_TOOLTIP_TEXT = (
    "This page provides an overview of all test orders.\n\n"
    "How to use this page:\n\n"
    "• Use the filters on the left or double-click a cell to quickly filter by that value.\n"
    "• !!NOTE!!: double clicking a cell resets all previous filters.\n"
    "• By clicking on the column headers you can sort the data.\n"
    "• Next to the column headers there are filter options for that column.\n"
    "• Download the table as CSV using the Download CSV button below the filters."
)

def order_overview_layout():
    return html.Div([
        html.Div([
            html.H2("Order Overview"),
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

        dcc.Store(id="order-data-store"),
        dcc.Store(id="order-cell-dblclick-store"),

        html.Div([
            html.Div([
                html.Label("Order ID:"),
                dcc.Dropdown(
                    id="order-order-id-filter",
                    options=[],
                    multi=True,
                    searchable=True,
                    clearable=True,
                    style={"width": "180px"}
                ),
                html.Label("Sample Name:"),
                dcc.Dropdown(
                    id="order-sample-name-filter",
                    options=[],
                    multi=True,
                    searchable=True,
                    clearable=True,
                    style={"width": "180px"}
                ),
                html.Label("Number of Cells:"),
                dcc.Dropdown(
                    id="order-number-of-cells-filter",
                    options=[],
                    multi=True,
                    searchable=True,
                    clearable=True,
                    style={"width": "180px"}
                ),
                html.Label("Testrig ID:"),
                dcc.Dropdown(
                    id="order-testrig-id-filter",
                    options=[],
                    multi=True,
                    searchable=True,
                    clearable=True,
                    style={"width": "180px"}
                ),
                html.Br(),
                html.Button([
                    html.I(className="bi bi-download", style={"marginRight": "8px", "fontSize": "1.2em"}),
                    "Download CSV"
                ], id="order-download-btn", n_clicks=0, className="download-btn", style={
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
                dcc.Download(id="order-download-csv"),
            ], style={"width": "200px", "display": "inline-block", "verticalAlign": "top", "marginRight": "20px"}),

            html.Div([
                dag.AgGrid(
                    id="order-order-table",
                    columnDefs=[
                        {"headerName": "Order ID", "field": "order_id", "type": "numeric", "filter": True, "sortable": True, "minWidth": 80},
                        {"headerName": "Sample Name", "field": "sample_name", "type": "text", "filter": True, "sortable": True, "minWidth": 120},
                        {"headerName": "# cells", "field": "number_of_cells", "type": "numeric", "filter": True, "sortable": True, "minWidth": 75},
                        {"headerName": "Testrig ID", "field": "testrig_id", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90},
                        {"headerName": "Short Description", "field": "short_description", "type": "text", "filter": True, "sortable": True, "minWidth": 140},
                        {"headerName": "Total [hr]", "field": "time_total", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90},
                        {"headerName": "Test [hr]", "field": "timeFacTest", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90},
                        {"headerName": "Run [hr]", "field": "timeFacRun", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90},
                        {"headerName": "start count", "field": "startCnt", "type": "numeric", "filter": True, "sortable": True, "minWidth": 80, "cellStyle": {"whiteSpace": "normal"}, "headerClass": "wrap-header"},
                        {"headerName": "polcurve count", "field": "polcurve_count", "type": "numeric", "filter": True, "sortable": True, "minWidth": 100, "cellStyle": {"whiteSpace": "normal"}, "headerClass": "wrap-header"},
                        {
                            "headerName": "Maximum values",
                            "headerClass": "centered-group-header",
                            "groupId": "maximumGroup",
                            "children": [
                                {"headerName": "jStack", "field": "jStack_max", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90},
                                {"headerName": "uCell", "field": "uCell_max", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90},
                                {"headerName": "tAndeIn", "field": "tAndeIn_max", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90, "columnGroupShow": "open"},
                                {"headerName": "tAndeOut", "field": "tAndeOut_max", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90, "columnGroupShow": "open"},
                                {"headerName": "pCtdeOut", "field": "pCtdeOut_max", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90, "columnGroupShow": "open"},
                                {"headerName": "pAndeIn", "field": "pAndeIn_max", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90, "columnGroupShow": "open"},
                                {"headerName": "vfAndeIn", "field": "vfAndeIn_max", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90, "columnGroupShow": "open"},
                                {"headerName": "mfH2Out", "field": "maxh2out", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90, "columnGroupShow": "open"}
                            ]
                        },
                    ],
                    rowData=[],
                    defaultColDef={
                        "resizable": True,
                        "sortable": True,
                        "filter": True,
                        "maxWidth": 140,
                        "flex": 1,
                        "cellStyle": {"fontSize": "12px", "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis"},
                    },
                    dashGridOptions={
                        "rowSelection": "single",
                        "animateRows": True,
                        "floatingFilter": True,
                        "groupDisplayType": "multipleColumns",
                        "rowClassRules": {
                            "ag-row-even": "params.node.rowIndex % 2 === 0",
                            "ag-row-odd": "params.node.rowIndex % 2 !== 0"
                        },
                        "icons": {
                            "filter": '''
                                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                                  <path d="M2 3H14L9.5 8.5V13L6.5 11V8.5L2 3Z" stroke="#666" stroke-width="1.5" fill="none"/>
                                </svg>
                            '''
                        }
                    },
                    style={"height": "calc(100vh - 300px)", "width": "100%"},
                    className="ag-theme-alpine",
                )
            ], style={"display": "inline-block", "width": "calc(100% - 240px)"}),
        ], style={"display": "flex", "flexDirection": "row"})
    ])

layout = order_overview_layout

# Lazy load data on page load
@callback(
    Output("order-data-store", "data"),
    Input("order-order-table", "id"),
)
def load_order_data(_):
    df = get_table_as_df("order_overview")
    if df.empty:
        return []
    # Round all _max columns and maxh2out to 2 decimals
    max_cols = [col for col in df.columns if col.endswith('_max')] + (["maxh2out"] if "maxh2out" in df.columns else [])
    if max_cols:
        df[max_cols] = df[max_cols].round(2)
    return df.to_dict("records")

# Update table and filter dropdowns
@callback(
    Output("order-order-table", "rowData"),
    Output("order-order-id-filter", "options"),
    Output("order-sample-name-filter", "options"),
    Output("order-number-of-cells-filter", "options"),
    Output("order-testrig-id-filter", "options"),
    Input("order-order-id-filter", "value"),
    Input("order-number-of-cells-filter", "value"),
    Input("order-sample-name-filter", "value"),
    Input("order-testrig-id-filter", "value"),
    Input("order-data-store", "data"),
    prevent_initial_call=True,
)
def update_table(order_id, number_of_cells, sample_name, testrig_id, data):
    if not data:
        return [], [], [], [], []
    df = pd.DataFrame(data)
    dff = df.copy()
    # Filtering logic
    if order_id:
        if isinstance(order_id, list):
            dff = dff[dff["order_id"].isin(order_id)]
        else:
            dff = dff[dff["order_id"] == order_id]
    if number_of_cells:
        if isinstance(number_of_cells, list):
            dff = dff[dff["number_of_cells"].isin(number_of_cells)]
        else:
            dff = dff[dff["number_of_cells"] == number_of_cells]
    if sample_name:
        sample_name_values = [None if v == "Null" else v for v in sample_name] if isinstance(sample_name, list) else [None if sample_name == "Null" else sample_name]
        dff = dff[dff["sample_name"].apply(lambda x: x if x is not None else "Null").isin([v if v is not None else "Null" for v in sample_name_values])]
    if testrig_id:
        testrig_id_values = [None if v == "Null" else v for v in testrig_id] if isinstance(testrig_id, list) else [None if testrig_id == "Null" else testrig_id]
        dff = dff[dff["testrig_id"].apply(lambda x: x if x is not None else "Null").isin([v if v is not None else "Null" for v in testrig_id_values])]
    records = dff.to_dict("records")
    if not records:
        records = [{}]

    # Now, update options for all dropdowns based on the filtered df
    filtered_df = df.copy()
    order_id_list = order_id if isinstance(order_id, list) else [order_id] if order_id is not None else None
    number_of_cells_list = number_of_cells if isinstance(number_of_cells, list) else [number_of_cells] if number_of_cells is not None else None
    sample_name_list = sample_name if isinstance(sample_name, list) else [sample_name] if sample_name is not None else None
    testrig_id_list = testrig_id if isinstance(testrig_id, list) else [testrig_id] if testrig_id is not None else None

    mask_order_id = filtered_df["order_id"].isin(order_id_list) if order_id_list else pd.Series([True] * len(filtered_df))
    mask_number_of_cells = filtered_df["number_of_cells"].isin(number_of_cells_list) if number_of_cells_list else pd.Series([True] * len(filtered_df))
    mask_sample_name = filtered_df["sample_name"].apply(lambda x: x if x is not None else "Null").isin([v if v is not None else "Null" for v in sample_name_list]) if sample_name_list else pd.Series([True] * len(filtered_df))
    mask_testrig_id = filtered_df["testrig_id"].apply(lambda x: x if x is not None else "Null").isin([v if v is not None else "Null" for v in testrig_id_list]) if testrig_id_list else pd.Series([True] * len(filtered_df))

    # Order ID options (apply all except order_id)
    mask = mask_number_of_cells & mask_sample_name & mask_testrig_id
    order_id_options = [
        {"label": str(oid), "value": oid}
        for oid in sorted(filtered_df[mask]["order_id"].dropna().unique(), reverse=True)
    ]
    # Sample Name options (apply all except sample_name)
    mask = mask_order_id & mask_number_of_cells & mask_testrig_id
    sample_name_options = [
        {"label": str(sname) if sname is not None else "Null", "value": str(sname) if sname is not None else "Null"}
        for sname in sorted(filtered_df[mask]["sample_name"].unique(), key=lambda x: (str(x) if x is not None else "Null"))
    ]
    # Number of Cells options (apply all except number_of_cells)
    mask = mask_order_id & mask_sample_name & mask_testrig_id
    number_of_cells_options = [
        {"label": str(int(nc)), "value": int(nc)}
        for nc in sorted(filtered_df[mask]["number_of_cells"].dropna().unique())
    ]
    # Testrig ID options (apply all except testrig_id)
    mask = mask_order_id & mask_number_of_cells & mask_sample_name
    testrig_id_options = [
        {"label": str(tid) if tid is not None else "Null", "value": str(tid) if tid is not None else "Null"}
        for tid in sorted(filtered_df[mask]["testrig_id"].unique(), key=lambda x: (str(x) if x is not None else "Null"))
    ]
    return records, order_id_options, sample_name_options, number_of_cells_options, testrig_id_options

# Callback to update filter dropdowns when a cell is double-clicked
@callback(
    Output("order-order-id-filter", "value"),
    Output("order-sample-name-filter", "value"),
    Output("order-number-of-cells-filter", "value"),
    Output("order-testrig-id-filter", "value"),
    Input("order-order-table", "cellDoubleClicked"),
    prevent_initial_call=True
)
def update_filter_on_cell_dblclick(cell):
    if not cell or "colId" not in cell or "value" not in cell:
        raise no_update
    col = cell["colId"]
    val = cell["value"]
    if col == "order_id":
        return val, None, None, None
    elif col == "sample_name":
        return None, str(val) if val is not None else "Null", None, None
    elif col == "number_of_cells":
        return None, None, int(val), None
    elif col == "testrig_id":
        return None, None, None, str(val) if val is not None else "Null"
    else:
        raise no_update

@callback(
    Output("order-download-csv", "data"),
    Input("order-download-btn", "n_clicks"),
    State("order-order-table", "rowData"),
    prevent_initial_call=True,
)
def download_order_table(n_clicks, table_data):
    if not table_data:
        return no_update
    df_filtered = pd.DataFrame(table_data)
    return dcc.express.send_data_frame(df_filtered.to_csv, "order_table.csv", index=False)