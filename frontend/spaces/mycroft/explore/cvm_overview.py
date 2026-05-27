from dash import dcc, callback, Output, Input, State, register_page, no_update, html
from dash.dcc.express import send_data_frame
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import plotly.express as px
import pandas as pd

from services.backend_service import get_tabular

register_page(
    __name__,
    path="/mycroft/data-exploration/cvm-overview",
    title="HOLMES - Mycroft - CVM Overview",
)

USAGE_BLOCKQUOTE_TEXT = [
    "Use filters to isolate CVM assembly or soaking populations.",
    "Color encodes result date for quick chronology review.",
    "Download CSV exports the filtered table data.",
]

TITLE_DICT = {
    "cvm_assembly": "CVM Assembly (process 362901)",
    "cvm_soaking": "CVM Soaking (process 453211)",
}

FILTER_COLUMN_MAP = {
    "stack": "stack_short_nr",
    "eol": "eol_type",
    "cells": "number_of_cells",
    "state": "location_result_state_description",
    "attr": "part_attribute_description",
    "measure": "cvm_measurement_type",
    "outlier": "cvm_outlier_detection",
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
    if "eol_type" in out.columns:
        out = out[out["eol_type"].isin(["cvm_assembly", "cvm_soaking"])]
    if "cvm_measurement_type" in out.columns:
        out = out[~out["cvm_measurement_type"].isin(["unknown", "no cvm data"])]
    if "result_date_utc" in out.columns:
        out["result_date_utc"] = pd.to_datetime(out["result_date_utc"], errors="coerce")
        out["result_date_utc"] = out["result_date_utc"].dt.strftime("%y-%m-%d %H:%M:%S")
    return out


def _filter_df(df, stack, eol, cells, state, part_attr, measure, outlier):
    dff = df.copy()
    if stack and "stack_short_nr" in dff.columns:
        dff = dff[dff["stack_short_nr"].isin(stack)]
    if eol and "eol_type" in dff.columns:
        dff = dff[dff["eol_type"].isin([eol])]
    if cells and "number_of_cells" in dff.columns:
        dff = dff[dff["number_of_cells"].isin(cells)]
    if state and "location_result_state_description" in dff.columns:
        dff = dff[dff["location_result_state_description"].isin(state)]
    if part_attr and "part_attribute_description" in dff.columns:
        dff = dff[dff["part_attribute_description"].isin(part_attr)]
    if measure and "cvm_measurement_type" in dff.columns:
        dff = dff[dff["cvm_measurement_type"].isin(measure)]
    if outlier and "cvm_outlier_detection" in dff.columns:
        dff = dff[dff["cvm_outlier_detection"].isin(outlier)]
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
                                dmc.Title("CVM Overview", order=2),
                                dmc.ActionIcon(
                                    DashIconify(icon="material-symbols:info-outline", width=20),
                                    id="myc-cvm-usage-toggle",
                                    variant="subtle",
                                    color="blue",
                                    size="md",
                                    radius="xl",
                                ),
                            ],
                        ),
                        dmc.Text("Cell voltage monitoring overview.", c="dimmed"),
                        dmc.Collapse(
                            dmc.Blockquote(
                                dmc.List(withPadding=False, children=[dmc.ListItem(item) for item in USAGE_BLOCKQUOTE_TEXT]),
                                color="blue",
                            ),
                            id="myc-cvm-usage-collapse",
                            opened=False,
                        ),
                    ],
                ),
                dcc.Store(id="myc-cvm-usage-open", data=False),
                dcc.Store(id="myc-cvm-data-store"),
                dcc.Download(id="myc-cvm-csv"),
                dmc.Paper(
                    withBorder=True,
                    p="md",
                    radius="md",
                    children=[
                        dmc.Stack(
                            gap="md",
                            children=[
                                dmc.SimpleGrid(
                                    cols={"base": 1, "md": 3},
                                    spacing="md",
                                    children=[
                                        dmc.InputWrapper(dcc.Dropdown(id="myc-cvm-stack", multi=True, style={"width": "100%"},placeholder="Select Stack Short Numbers"), label="Stack Short Number", htmlFor="myc-cvm-stack", className="dmc", styles={"label": {"marginBottom": "6px"}}),
                                        dmc.InputWrapper(dcc.Dropdown(id="myc-cvm-eol", value="cvm_assembly", clearable=False, style={"width": "100%"},placeholder="Select EOL Type"), label="EOL Type", htmlFor="myc-cvm-eol", className="dmc", styles={"label": {"marginBottom": "6px"}}),
                                        dmc.InputWrapper(dcc.Dropdown(id="myc-cvm-cells", multi=True, style={"width": "100%"},placeholder="Select Number of Cells"), label="Number of Cells", htmlFor="myc-cvm-cells", className="dmc", styles={"label": {"marginBottom": "6px"}}),
                                    ],
                                ),
                                dmc.SimpleGrid(
                                    cols={"base": 1, "md": 2, "lg": 4},
                                    spacing="md",
                                    children=[
                                        dmc.InputWrapper(dcc.Dropdown(id="myc-cvm-state", multi=True, style={"width": "100%"},placeholder="Select Location Result States"), label="Location Result State", htmlFor="myc-cvm-state", className="dmc", styles={"label": {"marginBottom": "6px"}}),
                                        dmc.InputWrapper(dcc.Dropdown(id="myc-cvm-attr", multi=True, style={"width": "100%"},placeholder="Select Part Attributes"), label="Part Attribute", htmlFor="myc-cvm-attr", className="dmc", styles={"label": {"marginBottom": "6px"}}),
                                        dmc.InputWrapper(dcc.Dropdown(id="myc-cvm-measure", multi=True, style={"width": "100%"},placeholder="Select CVM Measurement Types"), label="CVM Measurement Type", htmlFor="myc-cvm-measure", className="dmc", styles={"label": {"marginBottom": "6px"}}),
                                        dmc.InputWrapper(dcc.Dropdown(id="myc-cvm-outlier", multi=True, style={"width": "100%"},placeholder="Select CVM Outlier Detection Methods"), label="CVM Outlier Detection", htmlFor="myc-cvm-outlier", className="dmc", styles={"label": {"marginBottom": "6px"}}),
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
                            justify="flex-end",
                            align="center",
                            style={"padding": "6px 8px 2px 8px"},
                            children=[
                                dmc.Button(
                                    [
                                        html.I(className="bi bi-download", style={"marginRight": "6px", "fontSize": "0.9em"}),
                                        "CSV",
                                    ],
                                    id="myc-cvm-download",
                                    n_clicks=0,
                                    size="xs",
                                    variant="light",
                                    className="download-btn",
                                ),
                            ],
                        ),
                        dcc.Graph(id="myc-cvm-graph", style={"height": "100%", "width": "100%", "minHeight": 0, "flex": "1 1 0"}),
                    ],
                ),
            ],
        )
    ],
)


@callback(Output("myc-cvm-usage-open", "data"), Input("myc-cvm-usage-toggle", "n_clicks"), State("myc-cvm-usage-open", "data"), prevent_initial_call=True)
def toggle_usage(n, opened):
    if n is None:
        return no_update
    return not bool(opened)


@callback(Output("myc-cvm-usage-collapse", "opened"), Input("myc-cvm-usage-open", "data"))
def sync_usage(opened):
    return bool(opened)


@callback(
    Output("myc-cvm-data-store", "data"),
    Input("myc-cvm-stack", "id"),
    prevent_initial_call=False,
)
def init_data(_):
    df = _normalize_df(get_tabular("mycroft", "polcurve"))
    if df.empty:
        return []
    return df.to_dict("records")


@callback(
    Output("myc-cvm-stack", "options"),
    Output("myc-cvm-stack", "value"),
    Output("myc-cvm-eol", "options"),
    Output("myc-cvm-eol", "value"),
    Output("myc-cvm-cells", "options"),
    Output("myc-cvm-cells", "value"),
    Output("myc-cvm-state", "options"),
    Output("myc-cvm-state", "value"),
    Output("myc-cvm-attr", "options"),
    Output("myc-cvm-attr", "value"),
    Output("myc-cvm-measure", "options"),
    Output("myc-cvm-measure", "value"),
    Output("myc-cvm-outlier", "options"),
    Output("myc-cvm-outlier", "value"),
    Input("myc-cvm-data-store", "data"),
    Input("myc-cvm-stack", "value"),
    Input("myc-cvm-eol", "value"),
    Input("myc-cvm-cells", "value"),
    Input("myc-cvm-state", "value"),
    Input("myc-cvm-attr", "value"),
    Input("myc-cvm-measure", "value"),
    Input("myc-cvm-outlier", "value"),
)
def sync_filter_options(raw, stack, eol, cells, state, attr, measure, outlier):
    df = _normalize_df(pd.DataFrame(raw or []))
    if df.empty:
        return [], [], [], None, [], [], [], [], [], [], [], [], [], []

    selections = {
        "stack": stack,
        "eol": [eol] if eol else [],
        "cells": cells,
        "state": state,
        "attr": attr,
        "measure": measure,
        "outlier": outlier,
    }

    stack_opts, stack_val = _build_stateful_options(df, selections, "stack")
    eol_opts, eol_val = _build_stateful_options(df, selections, "eol")
    cells_opts, cells_val = _build_stateful_options(df, selections, "cells")
    state_opts, state_val = _build_stateful_options(df, selections, "state")
    attr_opts, attr_val = _build_stateful_options(df, selections, "attr")
    measure_opts, measure_val = _build_stateful_options(df, selections, "measure")
    outlier_opts, outlier_val = _build_stateful_options(df, selections, "outlier")

    eol_selected = eol_val[0] if eol_val else (eol_opts[0]["value"] if eol_opts else None)

    return (
        stack_opts,
        stack_val,
        eol_opts,
        eol_selected,
        cells_opts,
        cells_val,
        state_opts,
        state_val,
        attr_opts,
        attr_val,
        measure_opts,
        measure_val,
        outlier_opts,
        outlier_val,
    )


@callback(

    Output("myc-cvm-graph", "figure"),
    Input("myc-cvm-data-store", "data"),
    Input("myc-cvm-stack", "value"),
    Input("myc-cvm-eol", "value"),
    Input("myc-cvm-cells", "value"),
    Input("myc-cvm-state", "value"),
    Input("myc-cvm-attr", "value"),
    Input("myc-cvm-measure", "value"),
    Input("myc-cvm-outlier", "value"),
    Input("theme-store", "data"),
)
def update_graph(raw, stack, eol, cells, state, attr, measure, outlier, theme):
    template = "plotly_dark" if theme == "dark" else "plotly"
    df = _normalize_df(pd.DataFrame(raw or []))
    dff = _filter_df(df, stack, eol, cells, state, attr, measure, outlier)

    if dff.empty:
        return px.scatter(template=template)

    title = TITLE_DICT.get(eol, "CVM")
    fig = px.scatter(
        dff,
        x="curve_index" if "curve_index" in dff.columns else dff.columns[0],
        y="result_value" if "result_value" in dff.columns else dff.columns[0],
        template=template,
        color="result_date_utc" if "result_date_utc" in dff.columns else None,
        hover_data=[c for c in ["result_value", "curve_index", "location_result_state_description", "stack_short_nr", "cvm_measurement_type", "cvm_outlier_detection"] if c in dff.columns],
    )
    fig.update_yaxes(range=[-100, 300])
    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        title={"text": title, "x": 0.5, "pad": {"t": 8, "b": 0}},
        xaxis_title="cell number",
        yaxis_title="U_cell m-volt",
        legend_title_text="result_date_utc",
    )
    return fig


@callback(
    Output("myc-cvm-csv", "data"),
    Input("myc-cvm-download", "n_clicks"),
    State("myc-cvm-data-store", "data"),
    State("myc-cvm-stack", "value"),
    State("myc-cvm-eol", "value"),
    State("myc-cvm-cells", "value"),
    State("myc-cvm-state", "value"),
    State("myc-cvm-attr", "value"),
    State("myc-cvm-measure", "value"),
    State("myc-cvm-outlier", "value"),
    prevent_initial_call=True,
)
def download_csv(n_clicks, raw, stack, eol, cells, state, attr, measure, outlier):
    if not n_clicks:
        return no_update
    df = _normalize_df(pd.DataFrame(raw or []))
    dff = _filter_df(df, stack, eol, cells, state, attr, measure, outlier)
    return send_data_frame(dff.to_csv, "mycroft_cvm.csv", index=False)
