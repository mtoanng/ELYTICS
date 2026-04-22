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
    "Use the filters on the top or double-click a cell to quickly filter by that value.",
    "Double clicking a cell resets all previous filters.",
    "By clicking on the column headers you can sort the data.",
    "Next to the column headers there are filter options for that column.",
    "Download the table as CSV using the Download CSV button below the filters."
]

# Column metadata keeps field mapping in one place and avoids repetitive hard-coded dicts.
BASE_ORDER_COLUMNS = [
    ("Order ID", "order_id", "numeric"),
    ("Sample Name", "name", "text"),
    ("# cells", "number_of_cells", "numeric"),
    ("Testrig ID", "testrig_id", "numeric"),
    ("Short Description", "short_description", "text"),
    ("Total [hr]", "time_total", "numeric"),
    ("Test [hr]", "timeFacTest", "numeric"),
    ("Run [hr]", "timeFacRun", "numeric"),
    ("start count", "startCnt", "numeric"),
    ("polcurve count", "polcurve_count", "numeric"),
]

SAMPLE_DETAIL_COLUMNS = [
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


ORDER_COLUMN_SECTION_OPTIONS = [
    {
        "group": "Order columns",
        "items": [
            {"value": field, "label": header}
            for header, field, _ in BASE_ORDER_COLUMNS
        ],
    },
    {
        "group": "Sample details",
        "items": [
            {"value": field, "label": header}
            for header, field, _ in SAMPLE_DETAIL_COLUMNS
        ],
    },
    {
        "group": "Maximum values",
        "items": [
            {"value": field, "label": header}
            for header, field in MAX_GROUP_COLUMNS
        ],
    },
]
ORDER_COLUMN_SECTION_DEFAULT = [field for _, field, _ in BASE_ORDER_COLUMNS]


def _column_def(
    header: str,
    field: str,
    col_type: str,
    *,
    max_width: int | None = None,
    min_width: int | None = None,
) -> dict[str, Any]:
    is_numeric = col_type == "numeric"
    return {
        "headerName": header,
        "field": field,
        "type": col_type,
        "minWidth": min_width if min_width is not None else (90 if is_numeric else 120),
        "maxWidth": max_width if max_width is not None else (140 if is_numeric else 240),
        "wrapHeaderText": True,
        "autoHeaderHeight": True,
    }


def build_order_column_defs(selected_fields: set[str] | None = None):
    fields = selected_fields or set(ORDER_COLUMN_SECTION_DEFAULT)
    base_defs: list[dict[str, Any]] = [
        _column_def(
            header,
            field,
            col_type,
            max_width=320 if field == "short_description" else None,
        )
        for header, field, col_type in BASE_ORDER_COLUMNS
        if field in fields
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

    sample_children = [
        _column_def(
            header,
            field,
            col_type,
            max_width=300 if field == "description" else None,
        )
        for header, field, col_type in SAMPLE_DETAIL_COLUMNS
        if field in fields
    ]
    if sample_children:
        base_defs.append(
            {
                "headerName": "Sample details",
                "headerClass": "centered-group-header",
                "groupId": "sampleDetailsGroup",
                "children": sample_children,
            }
        )

    max_children = [child for child in max_children if child["field"] in fields]
    if max_children:
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
        style={
            "height": "calc(100dvh - var(--app-shell-header-offset, 0rem))",
            "display": "flex",
            "flexDirection": "column",
            "minHeight": 0,
        },
        children=[
            dmc.Stack(
                gap="md",
                style={"flex": "1 1 0", "minHeight": 0},
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
                    dcc.Store(id="order-data-store", data=None),
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
                                wrap="wrap",
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
                                        style={"flex": "1 1 160px", "minWidth": "160px"},
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
                                        style={"flex": "1 1 160px", "minWidth": "160px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="order-cell-name-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            searchable=True,
                                            clearable=True,
                                            placeholder="Select cell names",
                                            style={"width": "100%"},
                                        ),
                                        label="Cell Name",
                                        htmlFor="order-cell-name-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "1 1 160px", "minWidth": "160px"},
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
                                        style={"flex": "1 1 160px", "minWidth": "160px"},
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
                                        style={"flex": "1 1 160px", "minWidth": "160px"},
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
                                        style={"flex": "0 0 auto", "whiteSpace": "nowrap", "alignSelf": "flex-end"},
                                    ),
                                    dcc.Download(id="order-download-csv"),
                                ],
                            ),
                            dmc.Divider(size="xs", my="sm"),
                            dmc.MultiSelect(
                                id="order-visible-columns",
                                label="Visible Columns",
                                description="Hide or show columns. Sample and maximum value groups are hidden by default.",
                                data=ORDER_COLUMN_SECTION_OPTIONS,
                                value=ORDER_COLUMN_SECTION_DEFAULT,
                                searchable=True,
                                clearable=False,
                                nothingFoundMessage="No columns available",
                            ),
                            dmc.Space(h="sm"),
                            dmc.Box(
                                pos="relative",
                                style={
                                    "flex": "1 1 0",
                                    "minHeight": 0,
                                    "display": "flex",
                                    "width": "100%",
                                },
                                children=[
                                    dmc.LoadingOverlay(
                                        id="order-table-loading-overlay",
                                        visible=True,
                                        zIndex=10,
                                        overlayProps={"radius": "sm", "blur": 1},
                                    ),
                                    html.Div(
                                        id="order-table-grid-wrapper",
                                        style={
                                            "flex": "1 1 0",
                                            "minHeight": 0,
                                            "display": "flex",
                                            "width": "100%",
                                            "visibility": "hidden",
                                        },
                                        children=[
                                            dag.AgGrid(
                                                id="order-order-table",
                                                columnDefs=build_order_column_defs(),
                                                rowData=[],
                                                defaultColDef={
                                                    "resizable": True,
                                                    "sortable": True,
                                                    "filter": True,
                                                    "minWidth": 90,
                                                    "wrapHeaderText": True,
                                                    "autoHeaderHeight": True,
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
                                                style={"height": "100%", "width": "100%"},
                                            )
                                        ],
                                    ),
                                ],
                            )
                        ],
                    ),
                    html.Div(id="order-table-theme-dummy", style={"display": "none"}),
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
    # Order data now includes joined sample fields for cross-page consistency.
    df = get_tabular('sherlock', "order")
    if df.empty:
        return []
    # Round all _max columns and maxh2out to 2 decimals
    max_cols = [col for col in df.columns if col.endswith('_max')] + (["maxh2out"] if "maxh2out" in df.columns else [])
    if max_cols:
        df[max_cols] = df[max_cols].round(2)
    return df.to_dict("records")

# Populate filter dropdown options once when data loads (no re-fetch on filter change)
@callback(
    Output("order-order-id-filter", "options"),
    Output("order-sample-name-filter", "options"),
    Output("order-cell-name-filter", "options"),
    Output("order-number-of-cells-filter", "options"),
    Output("order-testrig-id-filter", "options"),
    Input("order-data-store", "data"),
)
def populate_filter_options(data):
    if data is None:
        raise PreventUpdate
    if not data:
        return [], [], [], [], []
    df = pd.DataFrame(data)
    order_id_options = [
        {"label": str(oid), "value": oid}
        for oid in sorted(df["order_id"].dropna().unique(), reverse=True)
    ]
    sample_name_options = [
        {
            "label": "Null" if pd.isna(sname) else str(sname),
            "value": "Null" if pd.isna(sname) else str(sname),
        }
        for sname in sorted(df["name"].unique(), key=lambda x: "Null" if pd.isna(x) else str(x))
    ]
    cell_name_options = [
        {"label": str(cn), "value": cn}
        for cn in sorted(df["cellunit_name"].dropna().unique())
    ]
    number_of_cells_options = [
        {"label": str(int(nc)), "value": int(nc)}
        for nc in sorted(df["number_of_cells"].dropna().unique())
    ]
    testrig_id_options = [
        {
            "label": "Null" if pd.isna(tid) else str(tid),
            "value": "Null" if pd.isna(tid) else str(tid),
        }
        for tid in sorted(df["testrig_id"].unique(), key=lambda x: "Null" if pd.isna(x) else str(x))
    ]
    return order_id_options, sample_name_options, cell_name_options, number_of_cells_options, testrig_id_options


# Client-side filtering — no server round-trip when filter values change
clientside_callback(
    """
    function(orderId, sampleName, cellName, numCells, testrigId, data) {
        if (data === null || data === undefined) {
            return window.dash_clientside.no_update;
        }
        if (!data.length) return [];
        var dff = data;
        if (orderId && orderId.length)
            dff = dff.filter(function(r) { return orderId.indexOf(r.order_id) !== -1; });
        if (sampleName && sampleName.length) {
            dff = dff.filter(function(r) {
                var v = (r.name == null) ? 'Null' : String(r.name);
                return sampleName.indexOf(v) !== -1;
            });
        }
        if (cellName && cellName.length)
            dff = dff.filter(function(r) { return cellName.indexOf(r.cellunit_name) !== -1; });
        if (numCells && numCells.length)
            dff = dff.filter(function(r) { return numCells.indexOf(r.number_of_cells) !== -1; });
        if (testrigId && testrigId.length) {
            dff = dff.filter(function(r) {
                var v = (r.testrig_id == null) ? 'Null' : String(r.testrig_id);
                return testrigId.indexOf(v) !== -1;
            });
        }
        return dff;
    }
    """,
    Output("order-order-table", "rowData"),
    Input("order-order-id-filter", "value"),
    Input("order-sample-name-filter", "value"),
    Input("order-cell-name-filter", "value"),
    Input("order-number-of-cells-filter", "value"),
    Input("order-testrig-id-filter", "value"),
    Input("order-data-store", "data"),
)


@callback(
    Output("order-table-loading-overlay", "visible"),
    Output("order-table-grid-wrapper", "style"),
    Input("order-data-store", "data"),
)
def sync_table_loading_state(data):
    base_style = {
        "flex": "1 1 0",
        "minHeight": 0,
        "display": "flex",
        "width": "100%",
    }
    if data is None:
        return True, {**base_style, "visibility": "hidden"}
    return False, {**base_style, "visibility": "visible"}

# Callback to update filter dropdowns when a cell is double-clicked
@callback(
    Output("order-order-id-filter", "value"),
    Output("order-sample-name-filter", "value"),
    Output("order-cell-name-filter", "value"),
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
        return [val], [], [], [], []
    if col == "name":
        return [], ["Null" if val is None else str(val)], [], [], []
    if col == "cellunit_name":
        return [], [], [val], [], []
    if col == "number_of_cells":
        return [], [], [], [int(val)], []
    if col == "testrig_id":
        return [], [], [], [], ["Null" if val is None else str(val)]
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
    Output("order-order-table", "columnDefs"),
    Input("order-visible-columns", "value"),
)
def update_column_sections(selected_sections):
    selected = set(selected_sections or [])
    if not selected:
        return []
    return build_order_column_defs(selected)

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