from dash import (
    html,
    dcc,
    callback,
    Output,
    Input,
    State,
    register_page,
    no_update,
    clientside_callback,
)
from dash.dcc.express import send_data_frame
import dash_mantine_components as dmc
import dash_ag_grid as dag
import pandas as pd
from dash.exceptions import PreventUpdate
from typing import Any
from dash_iconify import DashIconify

from services.backend_service import get_tabular

register_page(
    __name__,
    path="/sherlock/data-exploration/order-overview",
    title="HOLMES - Sherlock - Order Overview"
)

USAGE_BLOCKQUOTE_TEXT = [
    "Use the filters on the left or double-click a cell to quickly filter by that value.",
    "Double clicking a cell resets all previous filters.",
    "By clicking on the column headers you can sort the data.",
    "Next to the column headers there are filter options for that column.",
    "Download the table as CSV using the Download CSV button below the filters."
]

# Column metadata keeps field mapping in one place and avoids repetitive hard-coded dicts.
BASE_ORDER_COLUMNS = [
    ("Order ID", "order_id", "numeric"),
    ("Sample Name", "sample_name", "text"),
    ("# cells", "number_of_cells", "numeric"),
    ("Testrig ID", "testrig_id", "numeric"),
    ("Short Description", "short_description", "text"),
    ("Total [hr]", "time_total", "numeric"),
    ("Test [hr]", "timeFacTest", "numeric"),
    ("Run [hr]", "timeFacRun", "numeric"),
    ("start count", "startCnt", "numeric"),
    ("polcurve count", "polcurve_count", "numeric"),
]

MAX_GROUP_COLUMNS = [
    ("jStack", "jStack_max"),
    ("uCell", "uCell_max"),
    ("tAndeIn", "tAndeIn_max"),
    ("tAndeOut", "tAndeOut_max"),
    ("pCtdeOut", "pCtdeOut_max"),
    ("pAndeIn", "pAndeIn_max"),
    ("vfAndeIn", "vfAndeIn_max"),
    ("mfH2Out", "maxh2out"),
]


def build_order_column_defs():
    base_defs: list[dict[str, Any]] = [
        {"headerName": header, "field": field, "type": col_type}
        for header, field, col_type in BASE_ORDER_COLUMNS
    ]
    max_children: list[dict[str, Any]] = [
        {
            "headerName": header,
            "field": field,
            "type": "numeric",
            "columnGroupShow": "open" if idx >= 2 else None,
        }
        for idx, (header, field) in enumerate(MAX_GROUP_COLUMNS)
    ]
    # Drop None values so AG Grid receives a clean config.
    for child in max_children:
        if child["columnGroupShow"] is None:
            child.pop("columnGroupShow")

    base_defs.append(
        {
            "headerName": "Maximum values",
            "headerClass": "centered-group-header",
            "groupId": "maximumGroup",
            "children": max_children,
        }
    )
    return base_defs

def order_overview_layout():
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
                                    dmc.Title("Order Overview", order=2),
                                    dmc.ActionIcon(
                                        DashIconify(icon="material-symbols:info-outline", width=20),
                                        id="order-usage-toggle",
                                        variant="subtle",
                                        color="blue",
                                        size="md",
                                        radius="xl",
                                    ),
                                ],
                            ),
                            dmc.Text("This page provides an overview of all test orders.", c="dimmed"),
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
                                opened=False,
                                id="order-usage-collapse",
                            ),
                        ],
                    ),
                    dcc.Store(id="order-usage-open", data=False),
                    dcc.Store(id="order-data-store"),
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
                                            id="order-order-id-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            searchable=True,
                                            clearable=True,
                                            placeholder="Select order IDs",
                                            style={"width": "100%"},
                                        ),
                                        label="Order ID",
                                        htmlFor="order-order-id-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "0 0 220px", "minWidth": "220px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="order-sample-name-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            searchable=True,
                                            clearable=True,
                                            placeholder="Select sample names",
                                            style={"width": "100%"},
                                        ),
                                        label="Sample Name",
                                        htmlFor="order-sample-name-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "0 0 220px", "minWidth": "220px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="order-number-of-cells-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            searchable=True,
                                            clearable=True,
                                            placeholder="Select # of cells",
                                            style={"width": "100%"},
                                        ),
                                        label="Number of Cells",
                                        htmlFor="order-number-of-cells-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "0 0 220px", "minWidth": "220px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="order-testrig-id-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            searchable=True,
                                            clearable=True,
                                            placeholder="Select testrig IDs",
                                            style={"width": "100%"},
                                        ),
                                        label="Testrig ID",
                                        htmlFor="order-testrig-id-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "0 0 220px", "minWidth": "220px"},
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
                                        id="order-download-btn",
                                        n_clicks=0,
                                        className="download-btn",
                                        style={"flex": "0 0 auto", "whiteSpace": "nowrap"},
                                    ),
                                    dcc.Download(id="order-download-csv"),
                                ],
                            )
                        ],
                    ),
                    dmc.Paper(
                        withBorder=True,
                        p="md",
                        radius="md",
                        children=[
                            dcc.Loading(
                                id="order-table-loading",
                                type="default",
                                children=[
                                    dag.AgGrid(
                                        id="order-order-table",
                                        columnDefs=build_order_column_defs(),
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
                                            "theme": {
                                                "function": (
                                                    "themeQuartz.withParams({"
                                                    "accentColor: 'var(--mantine-primary-color-filled)', "
                                                    "fontFamily: 'var(--mantine-font-family)', "
                                                    "headerFontWeight: 'bold'"
                                                    "})"
                                                )
                                            },
                                        },
                                        style={"height": "calc(100vh - 330px)", "width": "100%"},
                                    )
                                ],
                            )
                        ],
                    ),
                    html.Div(id="order-table-theme-dummy"),
                ],
            )
        ],
    )

layout = order_overview_layout

# Lazy load data on page load
@callback(
    Output("order-data-store", "data"),
    Input("order-order-table", "id"),
)
def load_order_data(_):
    df = get_tabular('sherlock', "order")
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
)
def update_table(order_id, number_of_cells, sample_name, testrig_id, data):
    if not data:
        return [], [], [], [], []

    def as_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    df = pd.DataFrame(data)
    dff = df.copy()
    order_id_list = as_list(order_id)
    number_of_cells_list = as_list(number_of_cells)
    sample_name_list = as_list(sample_name)
    testrig_id_list = as_list(testrig_id)

    # Filtering logic
    if order_id_list:
        dff = dff[dff["order_id"].isin(order_id_list)]
    if number_of_cells_list:
        dff = dff[dff["number_of_cells"].isin(number_of_cells_list)]
    if sample_name_list:
        sample_name_keys = [str(v) for v in sample_name_list]
        dff = dff[
            dff["sample_name"].apply(lambda x: "Null" if pd.isna(x) else str(x)).isin(sample_name_keys)
        ]
    if testrig_id_list:
        testrig_keys = [str(v) for v in testrig_id_list]
        dff = dff[
            dff["testrig_id"].apply(lambda x: "Null" if pd.isna(x) else str(x)).isin(testrig_keys)
        ]

    records = dff.to_dict("records")

    # Now, update options for all dropdowns based on the filtered df
    filtered_df = df.copy()
    true_mask = pd.Series([True] * len(filtered_df), index=filtered_df.index)
    mask_order_id = filtered_df["order_id"].isin(order_id_list) if order_id_list else true_mask
    mask_number_of_cells = (
        filtered_df["number_of_cells"].isin(number_of_cells_list)
        if number_of_cells_list
        else true_mask
    )
    sample_name_keys = [str(v) for v in sample_name_list]
    mask_sample_name = (
        filtered_df["sample_name"].apply(lambda x: "Null" if pd.isna(x) else str(x)).isin(sample_name_keys)
        if sample_name_list
        else true_mask
    )
    testrig_keys = [str(v) for v in testrig_id_list]
    mask_testrig_id = (
        filtered_df["testrig_id"].apply(lambda x: "Null" if pd.isna(x) else str(x)).isin(testrig_keys)
        if testrig_id_list
        else true_mask
    )

    # Order ID options (apply all except order_id)
    mask = mask_number_of_cells & mask_sample_name & mask_testrig_id
    order_id_options = [
        {"label": str(oid), "value": oid}
        for oid in sorted(filtered_df[mask]["order_id"].dropna().unique(), reverse=True)
    ]
    # Sample Name options (apply all except sample_name)
    mask = mask_order_id & mask_number_of_cells & mask_testrig_id
    sample_name_options = [
        {
            "label": "Null" if pd.isna(sname) else str(sname),
            "value": "Null" if pd.isna(sname) else str(sname),
        }
        for sname in sorted(
            filtered_df[mask]["sample_name"].unique(),
            key=lambda x: "Null" if pd.isna(x) else str(x),
        )
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
        {
            "label": "Null" if pd.isna(tid) else str(tid),
            "value": "Null" if pd.isna(tid) else str(tid),
        }
        for tid in sorted(
            filtered_df[mask]["testrig_id"].unique(),
            key=lambda x: "Null" if pd.isna(x) else str(x),
        )
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
        raise PreventUpdate
    col = cell["colId"]
    val = cell["value"]
    if col == "order_id":
        return [val], [], [], []
    if col == "sample_name":
        return [], ["Null" if val is None else str(val)], [], []
    if col == "number_of_cells":
        return [], [], [int(val)], []
    if col == "testrig_id":
        return [], [], [], ["Null" if val is None else str(val)]
    raise PreventUpdate

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
    return send_data_frame(df_filtered.to_csv, "order_table.csv", index=False)

@callback(
    Output("order-usage-open", "data"),
    Input("order-usage-toggle", "n_clicks"),
    State("order-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage_blockquote(n_clicks, is_open):
    if n_clicks is None:
        return no_update
    return not bool(is_open)


@callback(
    Output("order-usage-collapse", "opened"),
    Input("order-usage-open", "data"),
)
def sync_usage_blockquote(is_open):
    return bool(is_open)

# Clientside callback to update AG Grid theme based on Mantine color scheme
clientside_callback(
    """
    (theme) => {
       document.documentElement.setAttribute('data-ag-theme-mode', theme === 'dark' ? 'dark' : 'light');
       return window.dash_clientside.no_update;
    }
    """,
    Output("order-table-theme-dummy", "children"),
    Input("theme-store", "data"),
)