import dash
from dash import html, dcc, Input, Output, State, callback, register_page
from dash.exceptions import PreventUpdate
import dash_ag_grid as dag
import pandas as pd
from services.backend_service import get_table_as_df

register_page(
    __name__, 
    path="/sherlock/data-exploration/sample-overview", 
    title="HOLMES - Sherlock - Sample Overview"
)

USAGE_TOOLTIP_TEXT = (
    "This page provides an overview of all samples.\n\n"
    "How to use this page:\n\n"
    "• Use the filters on the left or double-click a cell to quickly filter by that value.\n"
    "• !!NOTE!!: double clicking a cell resets all previous filters.\n"
    "• By clicking on the column headers you can sort the data.\n"
    "• Next to the column headers there are filter options for that column.\n"
    "• Download the table as CSV using the Download CSV button below the filters."
)

def sample_overview_layout():
    return html.Div([
        html.Div([
            html.H2("Sample Overview"),
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

        dcc.Store(id="sample-data-store"),
        dcc.Store(id="sample-cell-dblclick-store"),

        html.Div([
            html.Div([
                html.Label("Order ID:"),
                dcc.Dropdown(
                    id="sample-order-id-filter",
                    options=[],
                    multi=True,
                    searchable=True,
                    clearable=True,
                    style={"width": "180px"}
                ),
                html.Label("Sample Name:"),
                dcc.Dropdown(
                    id="sample-sample-name-filter",
                    options=[],
                    multi=True,
                    searchable=True,
                    clearable=True,
                    style={"width": "180px"}
                ),
                html.Label("Cell Name:"),
                dcc.Dropdown(
                    id="sample-cell-name-filter",
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
                ], id="sample-download-btn", n_clicks=0, className="download-btn", style={
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
                dcc.Download(id="sample-download-csv"),
            ], style={"width": "200px", "display": "inline-block", "verticalAlign": "top", "marginRight": "20px"}),

            html.Div([
                dag.AgGrid(
                    id="sample-sample-table",
                    columnDefs=[
                        {"headerName": "Sample name", "field": "name", "type": "text", "filter": True, "sortable": True, "minWidth": 110},
                        {"headerName": "Leepa number", "field": "leepa_number", "type": "text", "filter": True, "sortable": True, "minWidth": 120},
                        {"headerName": "Type", "field": "type", "type": "text", "filter": True, "sortable": True, "minWidth": 65},
                        {"headerName": "State", "field": "state", "type": "text", "filter": True, "sortable": True, "minWidth": 65},
                        {"headerName": "Plant", "field": "production_plant", "type": "text", "filter": True, "sortable": True, "minWidth": 60},
                        {"headerName": "Cell description", "field": "description", "type": "text", "filter": True, "sortable": True, "minWidth": 120},
                        {"headerName": "Cell name", "field": "cellunit_name", "type": "text", "filter": True, "sortable": True, "minWidth": 90},
                        {"headerName": "CCM", "field": "ccm_name", "type": "text", "filter": True, "sortable": True, "minWidth": 75},
                        {"headerName": "PTL", "field": "ptl_name", "type": "text", "filter": True, "sortable": True, "minWidth": 75},
                        {"headerName": "GDL", "field": "gdl_name", "type": "text", "filter": True, "sortable": True, "minWidth": 75},
                        {"headerName": "Active area / cell", "field": "active_area_per_cell", "type": "numeric", "filter": True, "sortable": True, "minWidth": 130},
                        {"headerName": "Order id", "field": "order_id", "type": "numeric", "filter": True, "sortable": True, "minWidth": 90},
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

layout = sample_overview_layout

# Lazy load data on page load
@callback(
    Output("sample-data-store", "data"),
    Input("sample-sample-table", "id"),
)
def load_order_data(_):
    df = get_table_as_df('sherlock', "sample_overview")
    if df.empty:
        return []
    # Round active_area_per_cell column values to 3 decimals
    if "active_area_per_cell" in df.columns:
        df["active_area_per_cell"] = df["active_area_per_cell"].round(3)
    return df.to_dict("records")

@callback(
    Output("sample-sample-table", "rowData"),
    Output("sample-order-id-filter", "options"),
    Output("sample-sample-name-filter", "options"),
    Output("sample-cell-name-filter", "options"),
    Input("sample-order-id-filter", "value"),
    Input("sample-sample-name-filter", "value"),
    Input("sample-cell-name-filter", "value"),
    Input("sample-data-store", "data"),                   # When data loads
    prevent_initial_call=True,
)
def update_table(sample_order_id, sample_sample_name, sample_cell_name, data):
    if not data:
            return [], [], [], []
        
    df = pd.DataFrame(data)
    dff = df.copy()

    # Apply filters
    if sample_order_id:
        if isinstance(sample_order_id, list):
            dff = dff[dff["order_id"].isin(sample_order_id)]
        else:
            dff = dff[dff["order_id"] == sample_order_id]
    if sample_sample_name:
        if isinstance(sample_sample_name, list):
            dff = dff[dff["name"].isin(sample_sample_name)]
        else:
            dff = dff[dff["name"] == sample_sample_name]
    if sample_cell_name:
        if isinstance(sample_cell_name, list):
            dff = dff[dff["cellunit_name"].isin(sample_cell_name)]
        else:
            dff = dff[dff["cellunit_name"] == sample_cell_name]
    records = dff.to_dict("records")
    if not records:
        records = [{}]

    # Now, update options for all dropdowns based on the filtered df
    filtered_df = df.copy()
    mask_order_id = filtered_df["order_id"].isin(sample_order_id) if sample_order_id else pd.Series([True] * len(filtered_df))
    mask_sample_name = filtered_df["name"].isin(sample_sample_name) if sample_sample_name else pd.Series([True] * len(filtered_df))
    mask_cell_name = filtered_df["cellunit_name"].isin(sample_cell_name) if sample_cell_name else pd.Series([True] * len(filtered_df))

    # Order ID options (apply all except order_id)
    mask = mask_sample_name & mask_cell_name
    order_id_options = [
        {"label": str(oid), "value": oid}
        for oid in sorted(filtered_df[mask]["order_id"].dropna().unique(), reverse=True)
    ]
    # Sample Name options (apply all except sample_name)
    mask = mask_order_id & mask_cell_name
    sample_name_options = [
        {"label": str(sname), "value": sname}
        for sname in sorted(filtered_df[mask]["name"].dropna().unique())
    ]
    # Cell Name options (apply all except cell_name)
    mask = mask_order_id & mask_sample_name
    cell_name_options = [
        {"label": str(cn), "value": cn}
        for cn in sorted(filtered_df[mask]["cellunit_name"].dropna().unique())
    ]

    return records, order_id_options, sample_name_options, cell_name_options

@callback(
    Output("sample-download-csv", "data"),
    Input("sample-download-btn", "n_clicks"),
    State("sample-sample-table", "rowData"),
    prevent_initial_call=True,
)
def download_sample_table(n_clicks, table_data):
    if not table_data:
        return dash.no_update
    df_filtered = pd.DataFrame(table_data)
    return dcc.send_data_frame(df_filtered.to_csv, "sample_table.csv", index=False)

@callback(
    Output("sample-order-id-filter", "value"),
    Output("sample-sample-name-filter", "value"),
    Output("sample-cell-name-filter", "value"),
    Input("sample-sample-table", "cellDoubleClicked"),
    prevent_initial_call=True
)
def update_filter_on_cell_dblclick(cell):
    if not cell or "colId" not in cell:
        raise no_update
    
    col = cell["colId"]
    val = cell["value"]
    if col == "order_id":
        return [val], None, None
    elif col == "name":
        return None, [val], None
    elif col == "cellunit_name":
        return None, None, [val]
    else:
        raise PreventUpdate