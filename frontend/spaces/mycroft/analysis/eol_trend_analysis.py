from dash import dcc, callback, Output, Input, State, register_page, no_update, html
from dash.dcc.express import send_data_frame
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import plotly.express as px
import pandas as pd

from services.backend_service import get_tabular

register_page(
    __name__,
    path="/mycroft/data-analysis/eol-trend-analysis",
    title="HOLMES - Mycroft - EOL Trend Analysis",
)

USAGE_BLOCKQUOTE_TEXT = [
    "Use the filters to narrow datasets before plotting.",
    "Select plot parameters independently for each of the three graphs.",
    "Download the currently filtered dataset using Download CSV.",
]

PLOT_PARAMETER_OPTIONS = [
    "u_cell_avg",
    "u_cell_max",
    "u_cell_min",
    "u_cell_spread",
    "u_cell_maxavg",
    "c_h2_ino2",
    "t_an_diff",
    "p_an_diff",
    "mf_h2",
]

Y_AXIS_UNITS = {
    "u_cell_avg": "u_cell_avg [mV]",
    "u_cell_max": "u_cell_max [mV]",
    "u_cell_min": "u_cell_min [mV]",
    "u_cell_spread": "u_cell_spread [mV]",
    "u_cell_maxavg": "u_cell_maxavg [mV]",
    "c_h2_ino2": "c_h2_ino2 [vol%]",
    "t_an_diff": "t_an_diff [C]",
    "p_an_diff": "p_an_diff [bar]",
    "mf_h2": "mf_h2 [Nm3/hour]",
}


def _make_options(series: pd.Series):
    vals = series.dropna().unique().tolist()
    try:
        vals = sorted(vals, key=lambda x: str(x))
    except Exception:
        pass
    return [{"label": str(v), "value": v} for v in vals]


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "test_type" in out.columns and "eol_type" not in out.columns:
        out = out.rename(columns={"test_type": "eol_type"})
    if "result_date_local_ts" in out.columns:
        out["result_date_local_ts"] = pd.to_datetime(out["result_date_local_ts"], errors="coerce")
    return out


def _filter_df(df: pd.DataFrame, up, stack, cells, j_set, setpoint, eol):
    dff = df.copy()
    if up and "uniquepart_id" in dff.columns:
        dff = dff[dff["uniquepart_id"].isin(up)]
    if stack and "stack_short_nr" in dff.columns:
        dff = dff[dff["stack_short_nr"].isin(stack)]
    if cells and "number_of_cells" in dff.columns:
        dff = dff[dff["number_of_cells"].isin(cells)]
    if j_set and "j_set" in dff.columns:
        dff = dff[dff["j_set"].isin(j_set)]
    if setpoint and "setpoint_direction" in dff.columns:
        dff = dff[dff["setpoint_direction"].isin(setpoint)]
    if eol and "eol_type" in dff.columns:
        dff = dff[dff["eol_type"].isin(eol)]
    return dff


def _build_figure(dff: pd.DataFrame, y_col: str, theme: str):
    template = "plotly_dark" if theme == "dark" else "plotly"
    if dff.empty or y_col not in dff.columns:
        return px.scatter(template=template)

    x_col = "result_date_local_ts" if "result_date_local_ts" in dff.columns else dff.columns[0]
    if x_col == "result_date_local_ts":
        dff = dff.copy()
        dff[x_col] = dff[x_col].dt.strftime("%y-%m-%d %H:%M:%S")

    color_col = "stack_short_nr" if "stack_short_nr" in dff.columns else None
    hover_cols = [
        c
        for c in [
            y_col,
            "stack_short_nr",
            "mf_h2",
            "p_an_diff",
            "t_an_diff",
            "setpoint_direction",
            "u_cell_avg",
            "u_cell_max",
            "u_cell_min",
            "eol_type",
        ]
        if c in dff.columns
    ]

    fig = px.scatter(
        dff,
        x=x_col,
        y=y_col,
        color=color_col,
        template=template,
        hover_data=hover_cols,
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        title={"text": f"{y_col} vs date", "x": 0.5, "pad": {"t": 8, "b": 0}},
        xaxis_title="date",
        yaxis_title=Y_AXIS_UNITS.get(y_col, y_col),
        legend_title_text="Stack_short_nr",
    )
    return fig


layout = dmc.Container(
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
                                dmc.Title("EOL Trend Analysis", order=2),
                                dmc.ActionIcon(
                                    DashIconify(icon="material-symbols:info-outline", width=20),
                                    id="myc-eol-trend-usage-toggle",
                                    variant="subtle",
                                    color="blue",
                                    size="md",
                                    radius="xl",
                                ),
                            ],
                        ),
                        dmc.Text("Trend view for EOL measurements over time.", c="dimmed"),
                        dmc.Collapse(
                            dmc.Blockquote(
                                dmc.List(
                                    withPadding=False,
                                    children=[dmc.ListItem(item) for item in USAGE_BLOCKQUOTE_TEXT],
                                ),
                                color="blue",
                            ),
                            id="myc-eol-trend-usage-collapse",
                            opened=False,
                        ),
                    ],
                ),
                dcc.Store(id="myc-eol-trend-usage-open", data=False),
                dcc.Store(id="myc-eol-trend-data-store"),
                dcc.Download(id="myc-eol-trend-csv"),
                dmc.Paper(
                    withBorder=True,
                    p="md",
                    radius="md",
                    children=[
                        dmc.Stack(
                            gap="md",
                            children=[
                                dmc.SimpleGrid(
                                    cols={"base": 1, "md": 2},
                                    spacing="md",
                                    children=[
                                        dmc.InputWrapper(
                                            dcc.Dropdown(id="myc-eol-trend-stack-filter", multi=True, style={"width": "100%"},placeholder="Select one or more Stack Short Numbers",),
                                            label="Stack Short Number",
                                            htmlFor="myc-eol-trend-stack-filter",
                                            className="dmc",
                                            styles={"label": {"marginBottom": "6px"}},
                                        ),
                                        dmc.InputWrapper(
                                            dcc.Dropdown(id="myc-eol-trend-uniquepart-filter", multi=True, style={"width": "100%"}, placeholder="Select one or more Unique Part IDs"),
                                            label="Unique Part ID",
                                            htmlFor="myc-eol-trend-uniquepart-filter",
                                            className="dmc",
                                            styles={"label": {"marginBottom": "6px"}},
                                        ),
                                    ],
                                ),
                                dmc.SimpleGrid(
                                    cols={"base": 1, "md": 2, "lg": 4},
                                    spacing="md",
                                    children=[
                                        dmc.InputWrapper(
                                            dcc.Dropdown(id="myc-eol-trend-cells-filter", multi=True, style={"width": "100%"}, placeholder="Select one or more Number of Cells"),
                                            label="Number of Cells",
                                            htmlFor="myc-eol-trend-cells-filter",
                                            className="dmc",
                                            styles={"label": {"marginBottom": "6px"}},
                                        ),
                                        dmc.InputWrapper(
                                            dcc.Dropdown(id="myc-eol-trend-jset-filter", multi=True, style={"width": "100%"}, placeholder="Select one or more J Sets"),
                                            label="J Set",
                                            htmlFor="myc-eol-trend-jset-filter",
                                            className="dmc",
                                            styles={"label": {"marginBottom": "6px"}},
                                        ),
                                        dmc.InputWrapper(
                                            dcc.Dropdown(id="myc-eol-trend-eol-type-filter", multi=True, style={"width": "100%"}, placeholder="Select one or more EOL Types"),
                                            label="EOL Type",
                                            htmlFor="myc-eol-trend-eol-type-filter",
                                            className="dmc",
                                            styles={"label": {"marginBottom": "6px"}},
                                        ),
                                        dmc.InputWrapper(
                                            dcc.Dropdown(id="myc-eol-trend-setpoint-filter", multi=True, style={"width": "100%"}, placeholder="Select one or more Setpoint Directions"),
                                            label="Setpoint Direction",
                                            htmlFor="myc-eol-trend-setpoint-filter",
                                            className="dmc",
                                            styles={"label": {"marginBottom": "6px"}},
                                        ),
                                    ],
                                ),
                            ],
                        )
                    ],
                ),
                dmc.Paper(
                    withBorder=True,
                    p="xs",
                    radius="md",
                    children=[
                        dmc.Group(
                            justify="space-between",
                            align="center",
                            style={"padding": "6px 8px 2px 8px", "flexWrap": "wrap", "gap": "10px"},
                            children=[
                                dmc.Group(
                                    gap="xs",
                                    align="center",
                                    style={"flexWrap": "wrap"},
                                    children=[
                                        dmc.Text("Graph 1", size="sm", fw=600),
                                        dmc.Box(
                                            dcc.Dropdown(
                                                id="myc-eol-trend-plot-a",
                                                value="u_cell_avg",
                                                options=[{"label": p, "value": p} for p in PLOT_PARAMETER_OPTIONS],
                                                clearable=False,
                                                style={"width": "100%"},
                                            ),
                                            className="dmc",
                                            style={"width": "220px", "minWidth": "180px"},
                                        ),
                                        dmc.Text("Graph 2", size="sm", fw=600),
                                        dmc.Box(
                                            dcc.Dropdown(
                                                id="myc-eol-trend-plot-b",
                                                value="c_h2_ino2",
                                                options=[{"label": p, "value": p} for p in PLOT_PARAMETER_OPTIONS],
                                                clearable=False,
                                                style={"width": "100%"},
                                            ),
                                            className="dmc",
                                            style={"width": "220px", "minWidth": "180px"},
                                        ),
                                        dmc.Text("Graph 3", size="sm", fw=600),
                                        dmc.Box(
                                            dcc.Dropdown(
                                                id="myc-eol-trend-plot-c",
                                                value="p_an_diff",
                                                options=[{"label": p, "value": p} for p in PLOT_PARAMETER_OPTIONS],
                                                clearable=False,
                                                style={"width": "100%"},
                                            ),
                                            className="dmc",
                                            style={"width": "220px", "minWidth": "180px"},
                                        ),
                                    ],
                                ),
                                dmc.Button(
                                    [
                                        html.I(className="bi bi-download", style={"marginRight": "6px", "fontSize": "0.9em"}),
                                        "CSV",
                                    ],
                                    id="myc-eol-trend-download",
                                    n_clicks=0,
                                    size="xs",
                                    variant="light",
                                    className="download-btn",
                                ),
                            ],
                        ),
                        dmc.Divider(size="xs", my="sm"),
                        dcc.Graph(id="myc-eol-trend-graph-a"),
                        dcc.Graph(id="myc-eol-trend-graph-b"),
                        dcc.Graph(id="myc-eol-trend-graph-c"),
                    ],
                ),
            ],
        )
    ],
)


@callback(
    Output("myc-eol-trend-usage-open", "data"),
    Input("myc-eol-trend-usage-toggle", "n_clicks"),
    State("myc-eol-trend-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage(n_clicks, is_open):
    if n_clicks is None:
        return no_update
    return not bool(is_open)


@callback(
    Output("myc-eol-trend-usage-collapse", "opened"),
    Input("myc-eol-trend-usage-open", "data"),
)
def sync_usage(opened):
    return bool(opened)


@callback(
    Output("myc-eol-trend-data-store", "data"),
    Output("myc-eol-trend-stack-filter", "options"),
    Output("myc-eol-trend-stack-filter", "value"),
    Output("myc-eol-trend-uniquepart-filter", "options"),
    Output("myc-eol-trend-uniquepart-filter", "value"),
    Output("myc-eol-trend-cells-filter", "options"),
    Output("myc-eol-trend-cells-filter", "value"),
    Output("myc-eol-trend-jset-filter", "options"),
    Output("myc-eol-trend-jset-filter", "value"),
    Output("myc-eol-trend-eol-type-filter", "options"),
    Output("myc-eol-trend-eol-type-filter", "value"),
    Output("myc-eol-trend-setpoint-filter", "options"),
    Output("myc-eol-trend-setpoint-filter", "value"),
    Input("myc-eol-trend-stack-filter", "id"),
    prevent_initial_call=False,
)
def init_data(_):
    df = _normalize_df(get_tabular("mycroft", "eol"))
    if df.empty:
        return [], [], [], [], [], [], [], [], [], [], [], [], []

    stack_options = _make_options(df["stack_short_nr"]) if "stack_short_nr" in df.columns else []
    up_options = _make_options(df["uniquepart_id"]) if "uniquepart_id" in df.columns else []
    cells_options = _make_options(df["number_of_cells"]) if "number_of_cells" in df.columns else []
    jset_options = _make_options(df["j_set"]) if "j_set" in df.columns else []
    eol_options = _make_options(df["eol_type"]) if "eol_type" in df.columns else []
    setpoint_options = _make_options(df["setpoint_direction"]) if "setpoint_direction" in df.columns else []

    return (
        df.to_dict("records"),
        stack_options,
        [option["value"] for option in stack_options],
        up_options,
        [option["value"] for option in up_options],
        cells_options,
        [option["value"] for option in cells_options],
        jset_options,
        [option["value"] for option in jset_options],
        eol_options,
        [option["value"] for option in eol_options],
        setpoint_options,
        [option["value"] for option in setpoint_options],
    )


@callback(
    Output("myc-eol-trend-graph-a", "figure"),
    Output("myc-eol-trend-graph-b", "figure"),
    Output("myc-eol-trend-graph-c", "figure"),
    Input("myc-eol-trend-data-store", "data"),
    Input("myc-eol-trend-plot-a", "value"),
    Input("myc-eol-trend-plot-b", "value"),
    Input("myc-eol-trend-plot-c", "value"),
    Input("myc-eol-trend-uniquepart-filter", "value"),
    Input("myc-eol-trend-stack-filter", "value"),
    Input("myc-eol-trend-cells-filter", "value"),
    Input("myc-eol-trend-jset-filter", "value"),
    Input("myc-eol-trend-setpoint-filter", "value"),
    Input("myc-eol-trend-eol-type-filter", "value"),
    Input("theme-store", "data"),
)
def update_graphs(raw, pa, pb, pc, up, stack, cells, j_set, setpoint, eol, theme):
    df = _normalize_df(pd.DataFrame(raw or []))
    dff = _filter_df(df, up, stack, cells, j_set, setpoint, eol)
    return (
        _build_figure(dff, pa or "u_cell_avg", theme),
        _build_figure(dff, pb or "c_h2_ino2", theme),
        _build_figure(dff, pc or "p_an_diff", theme),
    )


@callback(
    Output("myc-eol-trend-csv", "data"),
    Input("myc-eol-trend-download", "n_clicks"),
    State("myc-eol-trend-data-store", "data"),
    State("myc-eol-trend-uniquepart-filter", "value"),
    State("myc-eol-trend-stack-filter", "value"),
    State("myc-eol-trend-cells-filter", "value"),
    State("myc-eol-trend-jset-filter", "value"),
    State("myc-eol-trend-setpoint-filter", "value"),
    State("myc-eol-trend-eol-type-filter", "value"),
    prevent_initial_call=True,
)
def download_csv(n_clicks, raw, up, stack, cells, j_set, setpoint, eol):
    if not n_clicks:
        return no_update
    df = _normalize_df(pd.DataFrame(raw or []))
    dff = _filter_df(df, up, stack, cells, j_set, setpoint, eol)
    return send_data_frame(dff.to_csv, "mycroft_eol_trend.csv", index=False)
