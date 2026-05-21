from dash import dcc, callback, Output, Input, State, register_page, no_update, html, clientside_callback
from dash.dcc.express import send_data_frame
import dash_mantine_components as dmc
import dash_ag_grid as dag
from dash_iconify import DashIconify
import pandas as pd

from services.backend_service import get_tabular

register_page(
    __name__,
    path="/mycroft/data-exploration/stack-overview",
    title="HOLMES - Mycroft - Stack Overview",
)

USAGE_BLOCKQUOTE_TEXT = [
    "Use dropdown filters to narrow stack and component records.",
    "Both tables stay synchronized with active stack filters.",
    "Use dedicated download buttons for stack and component CSV exports.",
]

STACK_COLUMNS = [
    {"headerName": "stack_short_nr", "field": "stack_short_nr", "type": "text", "minWidth": 120},
    {"headerName": "uniquepart_id", "field": "uniquepart_id", "type": "text", "minWidth": 150},
    {"headerName": "part_attribute_description", "field": "part_attribute_description", "type": "text", "minWidth": 180},
    {"headerName": "result_date_utc", "field": "result_date_utc", "type": "text", "minWidth": 160},
    {"headerName": "result_state_description", "field": "result_state_description", "type": "text", "minWidth": 170},
    {"headerName": "number_of_cells", "field": "number_of_cells", "type": "numeric", "minWidth": 130},
]

COMP_COLUMNS = [
    {"headerName": "stack_short_nr", "field": "stack_short_nr", "type": "text", "minWidth": 120},
    {"headerName": "uniquepart_id", "field": "uniquepart_id", "type": "text", "minWidth": 150},
    {"headerName": "componentclass", "field": "componentclass", "type": "text", "minWidth": 150},
    {"headerName": "component_type_number", "field": "component_type_number", "type": "text", "minWidth": 170},
    {"headerName": "componentidentifier", "field": "componentidentifier", "type": "text", "minWidth": 260},
    {"headerName": "batch", "field": "batch", "type": "text", "minWidth": 120},
]

DEFAULT_COL_DEF = {
    "resizable": True,
    "sortable": True,
    "filter": True,
    "minWidth": 110,
}

GRID_OPTIONS = {
    "animateRows": True,
    "pagination": True,
    "paginationPageSize": 20,
    "enableCellTextSelection": True,
    "theme": {
        "function": (
            "themeQuartz.withParams({"
            "accentColor: 'var(--mantine-primary-color-filled)', "
            "fontFamily: 'var(--mantine-font-family)', "
            "headerFontWeight: 'bold'"
            "})"
        )
    },
}


def _make_options(series: pd.Series):
    vals = series.dropna().unique().tolist()
    try:
        vals = sorted(vals, key=lambda x: str(x))
    except Exception:
        pass
    return [{"label": str(v), "value": v} for v in vals]


def _filter_df(df, up, cells, stack, state, part_attr):
    dff = df.copy()
    if up and "uniquepart_id" in dff.columns:
        dff = dff[dff["uniquepart_id"].isin(up)]
    if cells and "number_of_cells" in dff.columns:
        dff = dff[dff["number_of_cells"].isin(cells)]
    if stack and "stack_short_nr" in dff.columns:
        dff = dff[dff["stack_short_nr"].isin(stack)]
    if state and "result_state_description" in dff.columns:
        dff = dff[dff["result_state_description"].isin(state)]
    if part_attr and "part_attribute_description" in dff.columns:
        dff = dff[dff["part_attribute_description"].isin(part_attr)]
    return dff


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
            style={"flex": "1 1 0", "minHeight": 0},
            children=[
                dmc.Stack(
                    gap=2,
                    children=[
                        dmc.Group(
                            gap="xs",
                            align="center",
                            children=[
                                dmc.Title("Stack Overview", order=2),
                                dmc.ActionIcon(
                                    DashIconify(icon="material-symbols:info-outline", width=20),
                                    id="myc-stack-usage-toggle",
                                    variant="subtle",
                                    color="blue",
                                    size="md",
                                    radius="xl",
                                ),
                            ],
                        ),
                        dmc.Text("Stack and component overview with synchronized filters.", c="dimmed"),
                        dmc.Collapse(
                            dmc.Blockquote(
                                dmc.List(withPadding=False, children=[dmc.ListItem(item) for item in USAGE_BLOCKQUOTE_TEXT]),
                                color="blue",
                            ),
                            id="myc-stack-usage-collapse",
                            opened=False,
                        ),
                    ],
                ),
                dcc.Store(id="myc-stack-usage-open", data=False),
                dcc.Store(id="myc-stack-data-store"),
                dcc.Store(id="myc-component-data-store"),
                html.Div(id="myc-stack-table-theme-dummy", style={"display": "none"}),
                dmc.Paper(
                    withBorder=True,
                    p="md",
                    radius="md",
                    children=[
                        dmc.Group(
                            gap="md",
                            align="flex-end",
                            style={"flexWrap": "wrap"},
                            children=[
                                dmc.InputWrapper(dcc.Dropdown(id="myc-stack-id", multi=True, style={"width": "100%"},placeholder="Select Stack Short Numbers"), label="Stack Short Number", htmlFor="myc-stack-id", className="dmc", styles={"label": {"marginBottom": "6px"}}, style={"flex": "1", "minWidth": "180px"}),
                                dmc.InputWrapper(dcc.Dropdown(id="myc-stack-up", multi=True, style={"width": "100%"},placeholder="Select Unique Part IDs"), label="Unique Part ID", htmlFor="myc-stack-up", className="dmc", styles={"label": {"marginBottom": "6px"}}, style={"flex": "1", "minWidth": "180px"}),
                                dmc.InputWrapper(dcc.Dropdown(id="myc-stack-cells", multi=True, style={"width": "100%"},placeholder="Select Number of Cells"), label="Number of Cells", htmlFor="myc-stack-cells", className="dmc", styles={"label": {"marginBottom": "6px"}}, style={"flex": "1", "minWidth": "180px"}),
                                dmc.InputWrapper(dcc.Dropdown(id="myc-stack-state", multi=True, style={"width": "100%"},placeholder="Select Location Result States"), label="Location Result State desc.", htmlFor="myc-stack-state", className="dmc", styles={"label": {"marginBottom": "6px"}}, style={"flex": "1", "minWidth": "220px"}),
                                dmc.InputWrapper(dcc.Dropdown(id="myc-stack-part-attr", multi=True, style={"width": "100%"},placeholder="Select Part Attributes"), label="Part Attribute desc.", htmlFor="myc-stack-part-attr", className="dmc", styles={"label": {"marginBottom": "6px"}}, style={"flex": "1", "minWidth": "220px"}),
                                dcc.Download(id="myc-stack-csv"),
                                dcc.Download(id="myc-component-csv"),
                            ],
                        )
                    ],
                ),
                dmc.Paper(
                    withBorder=True,
                    p="md",
                    radius="md",
                    style={"flex": "1 1 0", "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
                    children=[
                        dmc.SimpleGrid(
                            cols={"base": 1, "lg": 2},
                            spacing="md",
                            style={"flex": "1 1 0", "minHeight": 0},
                            children=[
                                dmc.Stack(
                                    gap="xs",
                                    style={"minHeight": 0, "display": "flex", "flexDirection": "column"},
                                    children=[
                                        dmc.Group(
                                            justify="space-between",
                                            align="center",
                                            children=[
                                                dmc.Text("Stack Overview", fw=600, size="sm"),
                                                dmc.Button(
                                                    [
                                                        html.I(className="bi bi-download", style={"marginRight": "6px", "fontSize": "0.9em"}),
                                                        "CSV",
                                                    ],
                                                    id="myc-stack-download",
                                                    n_clicks=0,
                                                    size="xs",
                                                    variant="light",
                                                    className="download-btn",
                                                    style={"paddingLeft": "10px", "paddingRight": "10px"},
                                                ),
                                            ],
                                        ),
                                        dag.AgGrid(
                                            id="myc-stack-table",
                                            columnDefs=STACK_COLUMNS,
                                            rowData=[],
                                            defaultColDef=DEFAULT_COL_DEF,
                                            dashGridOptions=GRID_OPTIONS,
                                            style={"height": "100%", "width": "100%", "minHeight": 0, "flex": "1 1 0"},
                                        ),
                                    ],
                                ),
                                dmc.Stack(
                                    gap="xs",
                                    style={"minHeight": 0, "display": "flex", "flexDirection": "column"},
                                    children=[
                                        dmc.Group(
                                            justify="space-between",
                                            align="center",
                                            children=[
                                                dmc.Text("Components Overview", fw=600, size="sm"),
                                                dmc.Button(
                                                    [
                                                        html.I(className="bi bi-download", style={"marginRight": "6px", "fontSize": "0.9em"}),
                                                        "CSV",
                                                    ],
                                                    id="myc-component-download",
                                                    n_clicks=0,
                                                    size="xs",
                                                    variant="light",
                                                    className="download-btn",
                                                    style={"paddingLeft": "10px", "paddingRight": "10px"},
                                                ),
                                            ],
                                        ),
                                        dag.AgGrid(
                                            id="myc-component-table",
                                            columnDefs=COMP_COLUMNS,
                                            rowData=[],
                                            defaultColDef=DEFAULT_COL_DEF,
                                            dashGridOptions=GRID_OPTIONS,
                                            style={"height": "100%", "width": "100%", "minHeight": 0, "flex": "1 1 0"},
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
    ],
)


@callback(Output("myc-stack-usage-open", "data"), Input("myc-stack-usage-toggle", "n_clicks"), State("myc-stack-usage-open", "data"), prevent_initial_call=True)
def toggle_usage(n, opened):
    if n is None:
        return no_update
    return not bool(opened)


@callback(Output("myc-stack-usage-collapse", "opened"), Input("myc-stack-usage-open", "data"))
def sync_usage(opened):
    return bool(opened)


clientside_callback(
    """
    (theme) => {
       document.documentElement.setAttribute('data-ag-theme-mode', theme === 'dark' ? 'dark' : 'light');
       return window.dash_clientside.no_update;
    }
    """,
    Output("myc-stack-table-theme-dummy", "children"),
    Input("theme-store", "data"),
)


@callback(
    Output("myc-stack-data-store", "data"),
    Output("myc-component-data-store", "data"),
    Output("myc-stack-id", "options"),
    Output("myc-stack-up", "options"),
    Output("myc-stack-cells", "options"),
    Output("myc-stack-state", "options"),
    Output("myc-stack-part-attr", "options"),
    Input("myc-stack-id", "id"),
    prevent_initial_call=False,
)
def init_data(_):
    df_stack = get_tabular("mycroft", "stack")
    df_comp = get_tabular("mycroft", "component")
    if "result_date_utc" in df_stack.columns:
        dt = pd.to_datetime(df_stack["result_date_utc"], errors="coerce")
        df_stack["result_date_utc"] = dt.dt.strftime("%y-%m-%d %H:%M:%S")

    return (
        df_stack.to_dict("records"),
        df_comp.to_dict("records"),
        _make_options(df_stack["stack_short_nr"]) if "stack_short_nr" in df_stack.columns else [],
        _make_options(df_stack["uniquepart_id"]) if "uniquepart_id" in df_stack.columns else [],
        _make_options(df_stack["number_of_cells"]) if "number_of_cells" in df_stack.columns else [],
        _make_options(df_stack["result_state_description"]) if "result_state_description" in df_stack.columns else [],
        _make_options(df_stack["part_attribute_description"]) if "part_attribute_description" in df_stack.columns else [],
    )


@callback(
    Output("myc-stack-table", "rowData"),
    Output("myc-component-table", "rowData"),
    Input("myc-stack-data-store", "data"),
    Input("myc-component-data-store", "data"),
    Input("myc-stack-up", "value"),
    Input("myc-stack-cells", "value"),
    Input("myc-stack-id", "value"),
    Input("myc-stack-state", "value"),
    Input("myc-stack-part-attr", "value"),
)
def update_tables(stack_raw, comp_raw, up, cells, stack, state, part_attr):
    df_stack = pd.DataFrame(stack_raw or [])
    df_comp = pd.DataFrame(comp_raw or [])

    filtered_stack = _filter_df(df_stack, up, cells, stack, state, part_attr)
    if "uniquepart_id" in filtered_stack.columns and "uniquepart_id" in df_comp.columns:
        filtered_comp = df_comp[df_comp["uniquepart_id"].isin(filtered_stack["uniquepart_id"].dropna().unique())]
    else:
        filtered_comp = df_comp

    return filtered_stack.to_dict("records"), filtered_comp.to_dict("records")


@callback(
    Output("myc-stack-csv", "data"),
    Input("myc-stack-download", "n_clicks"),
    State("myc-stack-data-store", "data"),
    State("myc-stack-up", "value"),
    State("myc-stack-cells", "value"),
    State("myc-stack-id", "value"),
    State("myc-stack-state", "value"),
    State("myc-stack-part-attr", "value"),
    prevent_initial_call=True,
)
def download_stack_csv(n_clicks, stack_raw, up, cells, stack, state, part_attr):
    if not n_clicks:
        return no_update
    df_stack = pd.DataFrame(stack_raw or [])
    dff = _filter_df(df_stack, up, cells, stack, state, part_attr)
    return send_data_frame(dff.to_csv, "mycroft_stack.csv", index=False)


@callback(
    Output("myc-component-csv", "data"),
    Input("myc-component-download", "n_clicks"),
    State("myc-stack-data-store", "data"),
    State("myc-component-data-store", "data"),
    State("myc-stack-up", "value"),
    State("myc-stack-cells", "value"),
    State("myc-stack-id", "value"),
    State("myc-stack-state", "value"),
    State("myc-stack-part-attr", "value"),
    prevent_initial_call=True,
)
def download_component_csv(n_clicks, stack_raw, comp_raw, up, cells, stack, state, part_attr):
    if not n_clicks:
        return no_update
    df_stack = pd.DataFrame(stack_raw or [])
    df_comp = pd.DataFrame(comp_raw or [])
    dff = _filter_df(df_stack, up, cells, stack, state, part_attr)
    if "uniquepart_id" in dff.columns and "uniquepart_id" in df_comp.columns:
        df_comp = df_comp[df_comp["uniquepart_id"].isin(dff["uniquepart_id"].dropna().unique())]
    return send_data_frame(df_comp.to_csv, "mycroft_component.csv", index=False)
