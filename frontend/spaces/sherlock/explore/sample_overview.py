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

from services.backend_service import get_table_as_df

register_page(
    __name__, 
    path="/sherlock/data-exploration/sample-overview", 
    title="HOLMES - Sherlock - Sample Overview"
)

USAGE_BLOCKQUOTE_TEXT = [
    "Use the filters above or double-click a cell to quickly filter by that value.",
    "Double-clicking a cell resets all previous filters.",
    "Click column headers to sort the data.",
    "Use filter controls in the column headers for per-column filtering.",
    "Use Download CSV to export the currently filtered table."
]

# Column metadata keeps field mapping in one place and avoids repetitive hard-coded dicts.
SAMPLE_COLUMNS = [
    ("Sample name", "name", "text"),
    ("Leepa number", "leepa_number", "text"),
    ("Type", "type", "text"),
    ("State", "state", "text"),
    ("Plant", "production_plant", "text"),
    ("Cell description", "description", "text"),
    ("Cell name", "cellunit_name", "text"),
    ("CCM", "ccm_name", "text"),
    ("PTL", "ptl_name", "text"),
    ("GDL", "gdl_name", "text"),
    ("Active area / cell", "active_area_per_cell", "numeric"),
    ("Order id", "order_id", "numeric"),
]


def build_sample_column_defs():
    """Build column definitions from metadata to avoid repetitive hard-coded dicts."""
    return [
        {"headerName": header, "field": field, "type": col_type}
        for header, field, col_type in SAMPLE_COLUMNS
    ]

def sample_overview_layout():
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
                            dmc.Title("Sample Overview", order=2),
                            dmc.Text("This page provides an overview of all samples.", c="dimmed"),
                            dmc.Blockquote(
                                dmc.List(
                                    spacing=4,
                                    size="sm",
                                    styles={"root": {"margin": 0, "paddingLeft": "1.1rem"}},
                                    children=[
                                        dmc.ListItem(item)
                                        for item in USAGE_BLOCKQUOTE_TEXT
                                    ],
                                ),
                                color="blue",
                                radius="md",
                            ),
                        ],
                    ),
                    dcc.Store(id="sample-data-store"),
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
                                            id="sample-order-id-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            searchable=True,
                                            clearable=True,
                                            placeholder="Select order IDs",
                                            style={"width": "100%"},
                                        ),
                                        label="Order ID",
                                        htmlFor="sample-order-id-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "0 0 220px", "minWidth": "220px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="sample-sample-name-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            searchable=True,
                                            clearable=True,
                                            placeholder="Select sample names",
                                            style={"width": "100%"},
                                        ),
                                        label="Sample Name",
                                        htmlFor="sample-sample-name-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "0 0 220px", "minWidth": "220px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="sample-cell-name-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            searchable=True,
                                            clearable=True,
                                            placeholder="Select cell names",
                                            style={"width": "100%"},
                                        ),
                                        label="Cell Name",
                                        htmlFor="sample-cell-name-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "1", "minWidth": "220px"},
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
                                        id="sample-download-btn",
                                        n_clicks=0,
                                        className="download-btn",
                                        style={"flex": "0 0 auto", "whiteSpace": "nowrap"},
                                    ),
                                    dcc.Download(id="sample-download-csv"),
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
                                id="sample-table-loading",
                                type="default",
                                children=[
                                    dag.AgGrid(
                                        id="sample-sample-table",
                                        columnDefs=build_sample_column_defs(),
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
                    html.Div(id="sample-table-theme-dummy"),
                ],
            )
        ],
    )

layout = sample_overview_layout

# Lazy load data on page load
@callback(
    Output("sample-data-store", "data"),
    Input("sample-sample-table", "id"),
)
def load_sample_data(_):
    df = get_table_as_df("sherlock", "sample_overview")
    if df.empty:
        return []
    # Round active_area_per_cell column values to 3 decimals
    if "active_area_per_cell" in df.columns:
        df["active_area_per_cell"] = df["active_area_per_cell"].round(3)
    return df.to_dict("records")

# Update table and filter dropdowns
@callback(
    Output("sample-sample-table", "rowData"),
    Output("sample-order-id-filter", "options"),
    Output("sample-sample-name-filter", "options"),
    Output("sample-cell-name-filter", "options"),
    Input("sample-order-id-filter", "value"),
    Input("sample-sample-name-filter", "value"),
    Input("sample-cell-name-filter", "value"),
    Input("sample-data-store", "data"),
)
def update_table(order_id, sample_name, cell_name, data):
    if not data:
        return [], [], [], []

    def as_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    df = pd.DataFrame(data)
    dff = df.copy()
    order_id_list = as_list(order_id)
    sample_name_list = as_list(sample_name)
    cell_name_list = as_list(cell_name)

    # Filtering logic
    if order_id_list:
        dff = dff[dff["order_id"].isin(order_id_list)]
    if sample_name_list:
        dff = dff[dff["name"].isin(sample_name_list)]
    if cell_name_list:
        dff = dff[dff["cellunit_name"].isin(cell_name_list)]

    records = dff.to_dict("records")

    # Now, update options for all dropdowns based on the filtered df
    filtered_df = df.copy()
    true_mask = pd.Series([True] * len(filtered_df), index=filtered_df.index)
    mask_order_id = (
        filtered_df["order_id"].isin(order_id_list) if order_id_list else true_mask
    )
    mask_sample_name = (
        filtered_df["name"].isin(sample_name_list) if sample_name_list else true_mask
    )
    mask_cell_name = (
        filtered_df["cellunit_name"].isin(cell_name_list) if cell_name_list else true_mask
    )

    # Order ID options (apply all except order_id)
    mask = mask_sample_name & mask_cell_name
    order_id_options = [
        {"label": str(oid), "value": oid}
        for oid in sorted(filtered_df[mask]["order_id"].dropna().unique())
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
        return no_update
    df_filtered = pd.DataFrame(table_data)
    return send_data_frame(df_filtered.to_csv, "sample_table.csv", index=False)


# Clientside callback to update AG Grid theme based on Mantine color scheme
clientside_callback(
    """
    (theme) => {
       document.documentElement.setAttribute('data-ag-theme-mode', theme === 'dark' ? 'dark' : 'light');
       return window.dash_clientside.no_update;
    }
    """,
    Output("sample-table-theme-dummy", "children"),
    Input("theme-store", "data"),
)

# Callback to update filter dropdowns when a cell is double-clicked
@callback(
    Output("sample-order-id-filter", "value"),
    Output("sample-sample-name-filter", "value"),
    Output("sample-cell-name-filter", "value"),
    Input("sample-sample-table", "cellDoubleClicked"),
    prevent_initial_call=True,
)
def update_filter_on_cell_dblclick(cell):
    if not cell or "colId" not in cell or "value" not in cell:
        raise PreventUpdate
    col = cell["colId"]
    val = cell["value"]
    if col == "order_id":
        return [val], [], []
    if col == "name":
        return [], [val], []
    if col == "cellunit_name":
        return [], [], [val]
    raise PreventUpdate