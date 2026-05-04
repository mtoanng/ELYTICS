from dash import dcc, callback, Output, Input, State, register_page, no_update, html
from dash.dcc.express import send_data_frame
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import plotly.express as px
import pandas as pd

from services.backend_service import get_tabular

register_page(
    __name__,
    path="/mycroft/data-exploration/soaking-overview",
    title="HOLMES - Mycroft - Soaking Overview",
)

USAGE_BLOCKQUOTE_TEXT = [
    "Use filters to narrow the soaking population.",
    "Filter values remain constrained to valid combinations.",
    "Use plot controls above the graph to change parameter and x-axis.",
]

PLOT_PARAMETER_OPTIONS = [
    "Leakage Dry External",
    "Leakage Dry Internal",
    "Process Time Soaking Hot",
    "Process Time Soaking Cold",
    "Leakage Filling Internal 1",
    "Leakage Filling Internal 2",
    "Pressure Filling Internal",
    "Differential Test",
    "Leakage Filling External xx bar",
    "Vision Inspection Filling External xx bar",
    "Pressure Filling External 65 bar - Max./Min.",
    "Pressure Filling External 68 bar - Max./Min.",
    "Vision Inspection Filling External 65/58 bar",
    "Result Notified Body",
    "Leakage Filling External 41 bar",
]

PLOT_X_AXIS_OPTIONS = ["result_date_utc", "stack_short_nr"]

PLOT_PARAMETER_PROCESS_MAP = {
    "Leakage Dry External": ("423131", 1),
    "Leakage Dry Internal": ("423151", 5),
    "Process Time Soaking Hot": ("423221", 10),
    "Process Time Soaking Cold": ("423221", 11),
    "Leakage Filling Internal 1": ("423271", 21),
    "Leakage Filling Internal 2": ("423271", 63),
    "Pressure Filling Internal": ("423271", 42),
    "Differential Test": ("423291", 63),
    "Leakage Filling External xx bar": ("423331", 79),
    "Vision Inspection Filling External xx bar": ("423341", 79),
    "Pressure Filling External 65 bar - Max./Min.": ("423321", 80),
    "Pressure Filling External 68 bar - Max./Min.": ("423321", 81),
    "Vision Inspection Filling External 65/58 bar": ("423341", 81),
    "Result Notified Body": ("423361", 81),
    "Leakage Filling External 41 bar": ("423331", 82),
}

FILTER_COLUMN_MAP = {
    "stack": "stack_short_nr",
    "up": "uniquepart_id",
    "cells": "number_of_cells",
    "part_attr": "part_attribute_description",
    "location": "location_result_state_description",
}

Y_AXIS_UNITS = {
    "Leakage Dry External": "leakage [mbarl/s]",
    "Leakage Dry Internal": "leakage [mbarl/s]",
    "Process Time Soaking Hot": "process time [s]",
    "Process Time Soaking Cold": "process time [s]",
    "Leakage Filling Internal 1": "leakage [mbarl/s]",
    "Leakage Filling Internal 2": "leakage [mbarl/s]",
    "Leakage Filling External xx bar": "leakage [mbarl/s]",
    "Differential Test": "differential pressure [%]",
    "Pressure Filling Internal": "pressure [bar]",
    "Pressure Filling External 65 bar - Max./Min.": "pressure [bar]",
    "Pressure Filling External 68 bar - Max./Min.": "pressure [bar]",
    "Vision Inspection Filling External 65/58 bar": "result",
    "Vision Inspection Filling External xx bar": "result",
    "Result Notified Body": "result_state",
    "Leakage Filling External 41 bar": "leakage [mbarl/s]",
}


def _make_options(series: pd.Series):
    vals = series.dropna().unique().tolist()
    try:
        vals = sorted(vals, key=lambda x: str(x))
    except Exception:
        pass
    return [{"label": str(v), "value": v} for v in vals]


def _filter_df(df, up, stack, cells, part_attr, location):
    dff = df.copy()
    if up and "uniquepart_id" in dff.columns:
        dff = dff[dff["uniquepart_id"].isin(up)]
    if stack and "stack_short_nr" in dff.columns:
        dff = dff[dff["stack_short_nr"].isin(stack)]
    if cells and "number_of_cells" in dff.columns:
        dff = dff[dff["number_of_cells"].isin(cells)]
    if part_attr and "part_attribute_description" in dff.columns:
        dff = dff[dff["part_attribute_description"].isin(part_attr)]
    if location and "location_result_state_description" in dff.columns:
        dff = dff[dff["location_result_state_description"].isin(location)]
    return dff


def _subset_param(df: pd.DataFrame, selected_param: str):
    if selected_param is None:
        return df

    process_filter = PLOT_PARAMETER_PROCESS_MAP.get(selected_param)
    if not process_filter:
        return df

    process_number, process_step_number = process_filter
    dff = df.copy()

    if "process_number" in dff.columns:
        dff = dff[dff["process_number"].astype(str) == str(process_number)]
    if "process_step_number" in dff.columns:
        step_series = pd.to_numeric(dff["process_step_number"], errors="coerce")
        dff = dff[step_series == process_step_number]

    if "result_date_utc" in dff.columns:
        dff = dff.sort_values("result_date_utc")

    if dff.empty and "param_name" in df.columns:
        return df[df["param_name"] == selected_param]

    return dff


def _build_stateful_options(df: pd.DataFrame, selections: dict[str, list | None], key: str):
    col = FILTER_COLUMN_MAP[key]
    dff = df.copy()
    for other_key, other_col in FILTER_COLUMN_MAP.items():
        if other_key == key:
            continue
        selected = selections.get(other_key)
        if selected and other_col in dff.columns:
            dff = dff[dff[other_col].isin(selected)]

    if col not in dff.columns:
        return [], []

    options = _make_options(dff[col])
    allowed = {opt["value"] for opt in options}
    current = selections.get(key) or []
    clamped = [value for value in current if value in allowed]
    return options, clamped


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
                                dmc.Title("Soaking Overview", order=2),
                                dmc.ActionIcon(
                                    DashIconify(icon="material-symbols:info-outline", width=20),
                                    id="myc-soaking-usage-toggle",
                                    variant="subtle",
                                    color="blue",
                                    size="md",

                                    radius="xl",
                                ),
                            ],
                        ),
                        dmc.Text("Soaking process trends.", c="dimmed"),
                        dmc.Collapse(
                            dmc.Blockquote(
                                dmc.List(withPadding=False, children=[dmc.ListItem(item) for item in USAGE_BLOCKQUOTE_TEXT]),
                                color="blue",
                            ),
                            id="myc-soaking-usage-collapse",
                            opened=False,
                        ),
                    ],
                ),
                dcc.Store(id="myc-soaking-usage-open", data=False),
                dcc.Store(id="myc-soaking-data-store"),
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
                                        dmc.InputWrapper(dcc.Dropdown(id="myc-soaking-stack", multi=True, style={"width": "100%"}), label="Stack Short Number", htmlFor="myc-soaking-stack", className="dmc", styles={"label": {"marginBottom": "6px"}}),
                                        dmc.InputWrapper(dcc.Dropdown(id="myc-soaking-up", multi=True, style={"width": "100%"}), label="Unique Part ID", htmlFor="myc-soaking-up", className="dmc", styles={"label": {"marginBottom": "6px"}}),
                                    ],
                                ),
                                dmc.SimpleGrid(
                                    cols={"base": 1, "md": 3},
                                    spacing="md",
                                    children=[
                                        dmc.InputWrapper(dcc.Dropdown(id="myc-soaking-cells", multi=True, style={"width": "100%"}), label="Number of Cells", htmlFor="myc-soaking-cells", className="dmc", styles={"label": {"marginBottom": "6px"}}),
                                        dmc.InputWrapper(dcc.Dropdown(id="myc-soaking-part-attr", multi=True, style={"width": "100%"}), label="Part Attribute", htmlFor="myc-soaking-part-attr", className="dmc", styles={"label": {"marginBottom": "6px"}}),
                                        dmc.InputWrapper(dcc.Dropdown(id="myc-soaking-location", multi=True, style={"width": "100%"}), label="Location Result State", htmlFor="myc-soaking-location", className="dmc", styles={"label": {"marginBottom": "6px"}}),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
                dmc.Paper(
                    withBorder=True,
                    p="xs",
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
                            justify="space-between",
                            align="center",
                            style={"padding": "6px 8px 2px 8px", "flexWrap": "wrap", "gap": "10px"},
                            children=[
                                dmc.Group(
                                    gap="xs",
                                    align="center",
                                    style={"flexWrap": "wrap"},
                                    children=[
                                        dmc.Text("Plot Parameter", size="sm", fw=600),
                                        dmc.Select(
                                            id="myc-soaking-plot-param",
                                            value="Leakage Dry External",
                                            data=[{"label": p, "value": p} for p in PLOT_PARAMETER_OPTIONS],
                                            allowDeselect=False,
                                            searchable=True,
                                            style={"width": "320px", "minWidth": "240px"},
                                        ),
                                        dmc.Text("X-Axis", size="sm", fw=600),
                                        dmc.SegmentedControl(
                                            id="myc-soaking-x-axis",
                                            value="result_date_utc",
                                            data=[
                                                {"label": "Result Date", "value": "result_date_utc"},
                                                {"label": "Stack Short Number", "value": "stack_short_nr"},
                                            ],
                                            fullWidth=False,
                                            size="sm",
                                        ),
                                        dmc.Text("Legend", size="sm", fw=600),
                                        dmc.SegmentedControl(
                                            id="myc-soaking-legend-toggle",
                                            value="show",
                                            data=[
                                                {"label": "Show", "value": "show"},
                                                {"label": "Hide", "value": "hide"},
                                            ],
                                            fullWidth=False,
                                            size="sm",
                                        ),
                                    ],
                                ),
                                dmc.Group(
                                    justify="flex-end",
                                    children=[
                                        dmc.Button(
                                            [
                                                html.I(className="bi bi-download", style={"marginRight": "6px", "fontSize": "0.9em"}),
                                                "CSV",
                                            ],
                                            id="myc-soaking-download",
                                            n_clicks=0,
                                            size="xs",
                                            variant="light",
                                            className="download-btn",
                                        ),
                                        dcc.Download(id="myc-soaking-csv"),
                                    ],
                                ),
                            ],
                        ),
                        dcc.Graph(id="myc-soaking-trend", style={"height": "100%", "width": "100%", "minHeight": 0, "flex": "1 1 0"}),
                    ],
                ),
            ],
        )
    ],
)


@callback(Output("myc-soaking-usage-open", "data"), Input("myc-soaking-usage-toggle", "n_clicks"), State("myc-soaking-usage-open", "data"), prevent_initial_call=True)
def toggle_usage(n, opened):
    if n is None:
        return no_update
    return not bool(opened)


@callback(Output("myc-soaking-usage-collapse", "opened"), Input("myc-soaking-usage-open", "data"))
def sync_usage(opened):
    return bool(opened)


@callback(
    Output("myc-soaking-data-store", "data"),
    Input("myc-soaking-stack", "id"),
    prevent_initial_call=False,
)
def init_data(_):
    df = get_tabular("mycroft", "soaking")
    if df.empty:
        return []
    return df.to_dict("records")


@callback(
    Output("myc-soaking-stack", "options"),
    Output("myc-soaking-stack", "value"),
    Output("myc-soaking-up", "options"),
    Output("myc-soaking-up", "value"),
    Output("myc-soaking-cells", "options"),
    Output("myc-soaking-cells", "value"),
    Output("myc-soaking-part-attr", "options"),
    Output("myc-soaking-part-attr", "value"),
    Output("myc-soaking-location", "options"),
    Output("myc-soaking-location", "value"),
    Input("myc-soaking-data-store", "data"),
    Input("myc-soaking-stack", "value"),
    Input("myc-soaking-up", "value"),
    Input("myc-soaking-cells", "value"),
    Input("myc-soaking-part-attr", "value"),
    Input("myc-soaking-location", "value"),
)
def sync_filter_options(raw, stack, up, cells, part_attr, location):
    df = pd.DataFrame(raw or [])
    if df.empty:
        return [], [], [], [], [], [], [], [], [], []

    selections = {
        "stack": stack,
        "up": up,
        "cells": cells,
        "part_attr": part_attr,
        "location": location,
    }

    stack_opts, stack_val = _build_stateful_options(df, selections, "stack")
    up_opts, up_val = _build_stateful_options(df, selections, "up")
    cells_opts, cells_val = _build_stateful_options(df, selections, "cells")
    attr_opts, attr_val = _build_stateful_options(df, selections, "part_attr")
    loc_opts, loc_val = _build_stateful_options(df, selections, "location")

    return stack_opts, stack_val, up_opts, up_val, cells_opts, cells_val, attr_opts, attr_val, loc_opts, loc_val


@callback(
    Output("myc-soaking-trend", "figure"),
    Input("myc-soaking-data-store", "data"),
    Input("myc-soaking-up", "value"),
    Input("myc-soaking-stack", "value"),
    Input("myc-soaking-cells", "value"),
    Input("myc-soaking-part-attr", "value"),
    Input("myc-soaking-location", "value"),
    Input("myc-soaking-plot-param", "value"),
    Input("myc-soaking-x-axis", "value"),
    Input("myc-soaking-legend-toggle", "value"),
    Input("theme-store", "data"),
)
def update_graph(raw, up, stack, cells, part_attr, location, plot_param, x_axis, legend_toggle, theme):
    template = "plotly_dark" if theme == "dark" else "plotly"
    df = pd.DataFrame(raw or [])
    dff = _filter_df(df, up, stack, cells, part_attr, location)

    if dff.empty:
        return px.scatter(template=template)

    top_dff = _subset_param(dff, plot_param)
    if x_axis not in top_dff.columns:
        x_axis = "result_date_utc" if "result_date_utc" in top_dff.columns else top_dff.columns[0]

    trend = px.scatter(
        top_dff,
        x=x_axis,
        y="result_value" if "result_value" in top_dff.columns else top_dff.columns[0],
        color="param_name" if "param_name" in top_dff.columns else None,
        template=template,
        hover_data=[c for c in ["workcycle_counter", "result_date_utc", "param_name", "process_step_number"] if c in top_dff.columns],
    )
    trend.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        title={"text": f"{plot_param}", "x": 0.5, "pad": {"t": 8, "b": 0}},
        xaxis_title=("Result Date" if x_axis == "result_date_utc" else "Stack Short Number"),
        yaxis_title=Y_AXIS_UNITS.get(plot_param, plot_param),
        showlegend=(legend_toggle != "hide"),
        legend_title_text="",
        legend=dict(
            orientation="v",
            x=0.99,
            y=0.99,
            xanchor="right",
            yanchor="top",
            bgcolor="rgba(255,255,255,0.65)" if theme != "dark" else "rgba(0,0,0,0.45)",
            borderwidth=0,
        ),
    )
    return trend


@callback(
    Output("myc-soaking-csv", "data"),
    Input("myc-soaking-download", "n_clicks"),
    State("myc-soaking-data-store", "data"),
    State("myc-soaking-up", "value"),
    State("myc-soaking-stack", "value"),
    State("myc-soaking-cells", "value"),
    State("myc-soaking-part-attr", "value"),
    State("myc-soaking-location", "value"),
    prevent_initial_call=True,
)
def download_csv(n_clicks, raw, up, stack, cells, part_attr, location):
    if not n_clicks:
        return no_update
    df = pd.DataFrame(raw or [])
    dff = _filter_df(df, up, stack, cells, part_attr, location)
    return send_data_frame(dff.to_csv, "mycroft_soaking.csv", index=False)
