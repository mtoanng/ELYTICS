from dash import dcc, callback, Output, Input, State, register_page, no_update, html, ctx
from dash.dcc.express import send_data_frame
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from services.backend_service import get_tabular

register_page(
    __name__,
    path="/mycroft/data-exploration/eol-polcurve",
    title="HOLMES - Mycroft - EOL Polarization Curve",
)

USAGE_BLOCKQUOTE_TEXT = [
    "Use top filters to restrict stack and sample population.",
    "Choose x-axis and plot parameter to inspect behavior changes.",
    "Download CSV exports the currently filtered table.",
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
X_AXIS_OPTIONS = ["step", "time", "j-set", "j-set plot"]

FILTER_COLUMN_MAP = {
    "stack": "stack_short_nr",
    "up": "uniquepart_id",
    "eol": "eol_type",
    "setpoint": "setpoint_direction",
}


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "test_type" in out.columns and "eol_type" not in out.columns:
        out = out.rename(columns={"test_type": "eol_type"})
    if "result_date_local_ts" in out.columns:
        out["result_date_local_ts"] = pd.to_datetime(out["result_date_local_ts"], errors="coerce")
        out["result_date_local_ts"] = out["result_date_local_ts"].dt.strftime("%y-%m-%d %H:%M:%S")
    return out


def _make_options(series: pd.Series):
    vals = series.dropna().unique().tolist()
    try:
        vals = sorted(vals, key=lambda x: str(x))
    except Exception:
        pass
    return [{"label": str(v), "value": v} for v in vals]


def _x_param(selected_xaxis: str) -> str:
    if selected_xaxis == "j-set plot":
        return "j_set_plot"
    if selected_xaxis == "j-set":
        return "j_set"
    if selected_xaxis == "time":
        return "result_date_local_ts"
    return "step"


def _filter_df(df, up, stack, setpoint, eol):
    dff = df.copy()
    if up and "uniquepart_id" in dff.columns:
        dff = dff[dff["uniquepart_id"].isin(up)]
    if stack and "stack_short_nr" in dff.columns:
        dff = dff[dff["stack_short_nr"].isin(stack)]
    if eol and "eol_type" in dff.columns:
        dff = dff[dff["eol_type"].isin(eol)]
    if setpoint and "setpoint_direction" in dff.columns:
        dff = dff[dff["setpoint_direction"].isin(setpoint)]
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


def _option_values(options: list[dict]) -> list:
    return [option["value"] for option in options]


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
                                dmc.Title("EOL Polarization Curve", order=2),
                                dmc.ActionIcon(
                                    DashIconify(icon="material-symbols:info-outline", width=20),
                                    id="myc-polcurve-usage-toggle",
                                    variant="subtle",
                                    color="blue",
                                    size="md",
                                    radius="xl",
                                ),
                            ],
                        ),
                        dmc.Text("Overview of EOL polarization curves and related metrics.", c="dimmed"),
                        dmc.Collapse(
                            dmc.Blockquote(
                                dmc.List(withPadding=False, children=[dmc.ListItem(item) for item in USAGE_BLOCKQUOTE_TEXT]),
                                color="blue",
                            ),
                            id="myc-polcurve-usage-collapse",
                            opened=False,
                        ),
                    ],
                ),
                dcc.Store(id="myc-polcurve-usage-open", data=False),
                dcc.Store(id="myc-polcurve-data-store"),
                dcc.Store(id="myc-polcurve-defaults-applied", data=False),
                dcc.Download(id="myc-polcurve-csv"),
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
                                dmc.InputWrapper(dcc.Dropdown(id="myc-polcurve-stack", multi=True, style={"width": "100%"},placeholder="Select one or more Stack Short Numbers"), label="Stack Short Number", htmlFor="myc-polcurve-stack", className="dmc", styles={"label": {"marginBottom": "6px"}}, style={"flex": "1", "minWidth": "180px"}),
                                dmc.InputWrapper(dcc.Dropdown(id="myc-polcurve-up", multi=True, style={"width": "100%"}), label="Unique Part ID", htmlFor="myc-polcurve-up", className="dmc", styles={"label": {"marginBottom": "6px"}}, style={"flex": "1", "minWidth": "180px"}),
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
                                        dmc.Text("X Axis", size="sm", fw=600),
                                        dmc.Select(
                                            id="myc-polcurve-xaxis",
                                            value="step",
                                            data=[{"label": x, "value": x} for x in X_AXIS_OPTIONS],
                                            allowDeselect=False,
                                            style={"width": "220px", "minWidth": "180px"},
                                        ),
                                        dmc.Text("Plot Parameter", size="sm", fw=600),
                                        dmc.Select(
                                            id="myc-polcurve-plot-param",
                                            value="u_cell_avg",
                                            data=[{"label": p, "value": p} for p in PLOT_PARAMETER_OPTIONS],
                                            allowDeselect=False,
                                            style={"width": "260px", "minWidth": "200px"},
                                        ),
                                        dmc.Text("EOL Type", size="sm", fw=600),
                                        dmc.Box(
                                            dcc.Dropdown(
                                                id="myc-polcurve-eol",
                                                multi=True,
                                                style={"width": "100%"},
                                            ),
                                            className="dmc",
                                            style={"width": "220px", "minWidth": "180px"},
                                        ),
                                        dmc.Text("Setpoint", size="sm", fw=600),
                                        dmc.Box(
                                            dcc.Dropdown(
                                                id="myc-polcurve-setpoint",
                                                multi=True,
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
                                    id="myc-polcurve-download",
                                    n_clicks=0,
                                    size="xs",
                                    variant="light",
                                    className="download-btn",
                                ),
                            ],
                        ),
                        dmc.Divider(size="xs", my="sm"),
                        dcc.Graph(id="myc-polcurve-graph-1", style={"height": "38vh"}),
                        dcc.Graph(id="myc-polcurve-graph-2", style={"height": "38vh"}),
                        dcc.Graph(id="myc-polcurve-graph-3", style={"height": "38vh"}),
                    ],
                ),
            ],
        )
    ],
)


@callback(Output("myc-polcurve-usage-open", "data"), Input("myc-polcurve-usage-toggle", "n_clicks"), State("myc-polcurve-usage-open", "data"), prevent_initial_call=True)
def toggle_usage(n, opened):
    if n is None:
        return no_update
    return not bool(opened)


@callback(Output("myc-polcurve-usage-collapse", "opened"), Input("myc-polcurve-usage-open", "data"))
def sync_usage(opened):
    return bool(opened)


@callback(
    Output("myc-polcurve-data-store", "data"),
    Input("myc-polcurve-stack", "id"),
    prevent_initial_call=False,
)
def init_data(_):
    df = _normalize_df(get_tabular("mycroft", "eol"))
    if df.empty:
        return []
    return df.to_dict("records")


@callback(
    Output("myc-polcurve-stack", "options"),
    Output("myc-polcurve-stack", "value"),
    Output("myc-polcurve-up", "options"),
    Output("myc-polcurve-up", "value"),
    Output("myc-polcurve-eol", "options"),
    Output("myc-polcurve-eol", "value"),
    Output("myc-polcurve-setpoint", "options"),
    Output("myc-polcurve-setpoint", "value"),
    Output("myc-polcurve-defaults-applied", "data"),
    Input("myc-polcurve-data-store", "data"),
    Input("myc-polcurve-stack", "value"),
    Input("myc-polcurve-up", "value"),
    Input("myc-polcurve-eol", "value"),
    Input("myc-polcurve-setpoint", "value"),
    State("myc-polcurve-defaults-applied", "data"),
    prevent_initial_call=False,
)
def sync_filter_options(raw, stack, up, eol, setpoint, defaults_applied):
    df = _normalize_df(pd.DataFrame(raw or []))
    if df.empty:
        return [], [], [], [], [], [], [], [], defaults_applied

    selections = {
        "stack": stack,
        "up": up,
        "eol": eol,
        "setpoint": setpoint,
    }

    stack_opts, stack_val = _build_stateful_options(df, selections, "stack")
    up_opts, up_val = _build_stateful_options(df, selections, "up")
    eol_opts, eol_val = _build_stateful_options(df, selections, "eol")
    sp_opts, sp_val = _build_stateful_options(df, selections, "setpoint")

    if not defaults_applied:
        stack_val = _option_values(stack_opts)
        up_val = _option_values(up_opts)
        eol_val = _option_values(eol_opts)
        sp_val = _option_values(sp_opts)
        defaults_applied = True

    return stack_opts, stack_val, up_opts, up_val, eol_opts, eol_val, sp_opts, sp_val, defaults_applied


@callback(

    Output("myc-polcurve-graph-1", "figure"),
    Output("myc-polcurve-graph-2", "figure"),
    Output("myc-polcurve-graph-3", "figure"),
    Input("myc-polcurve-data-store", "data"),
    Input("myc-polcurve-up", "value"),
    Input("myc-polcurve-stack", "value"),
    Input("myc-polcurve-setpoint", "value"),
    Input("myc-polcurve-eol", "value"),
    Input("myc-polcurve-xaxis", "value"),
    Input("myc-polcurve-plot-param", "value"),
    Input("theme-store", "data"),
)
def update_graphs(raw, up, stack, setpoint, eol, selected_x, plot_param, theme):
    template = "plotly_dark" if theme == "dark" else "plotly"
    df = _normalize_df(pd.DataFrame(raw or []))
    dff = _filter_df(df, up, stack, setpoint, eol)
    if dff.empty:
        empty = px.scatter(template=template)
        return empty, empty, empty

    x_param = _x_param(selected_x)
    if x_param not in dff.columns:
        x_param = dff.columns[0]

    fig1 = px.scatter(template=template)
    if all(c in dff.columns for c in ["u_cell_min", "u_cell_max", "u_cell_avg"]):
        fig1.add_trace(go.Scatter(x=dff[x_param], y=dff["u_cell_min"], mode="markers", marker=dict(color="green"), name="U_cell_Min", opacity=0.5))
        fig1.add_trace(go.Scatter(x=dff[x_param], y=dff["u_cell_max"], mode="markers", marker=dict(color="yellow"), name="U_cell_Max", opacity=0.5))
        fig1.add_trace(go.Scatter(x=dff[x_param], y=dff["u_cell_avg"], mode="markers", marker=dict(color="blue"), name="U_cell_Avg", opacity=0.5))
    fig1.add_hline(y=1480, line_dash="solid", line_color="grey", annotation_text="PoleCurve1_low(65deg)", annotation_position="top right", annotation_font_color="grey")
    fig1.add_hline(y=1890, line_dash="solid", line_color="grey", annotation_text="PoleCurve1_mid(65deg)", annotation_position="top right", annotation_font_color="grey")
    fig1.add_hline(y=2100, line_dash="solid", line_color="grey", annotation_text="PoleCurve1_high(65deg)", annotation_position="top right", annotation_font_color="grey")
    fig1.update_yaxes(range=[1450, 2150])
    fig1.update_layout(margin=dict(l=20, r=20, t=40, b=20), title={"text": "polcurve_normal_temp", "x": 0.5, "pad": {"t": 8, "b": 0}}, xaxis_title=x_param, yaxis_title="U_cell m-volt", legend_title_text="Variable")

    pp = plot_param or "u_cell_avg"
    fig2 = px.scatter(template=template)
    if pp in dff.columns:
        fig2.add_trace(go.Scatter(x=dff[x_param], y=dff[pp], mode="markers", marker=dict(color="blue"), name=pp, yaxis="y1"))
    if "j_set" in dff.columns:
        fig2.add_trace(go.Scatter(x=dff[x_param], y=dff["j_set"], mode="markers", marker=dict(color="red"), name="j_set", yaxis="y2"))
    fig2.update_layout(
        yaxis=dict(title=f"{pp}"),
        yaxis2=dict(title="j_set", overlaying="y", side="right"),
        legend=dict(title="y-axis"),
        title={"text": f"measurement vs. {pp} and {x_param}", "x": 0.5, "pad": {"t": 8, "b": 0}},
        template=template,
    )

    fig3 = px.scatter(
        dff,
        x=x_param,
        y=pp if pp in dff.columns else dff.columns[0],
        template=template,
        color="stack_short_nr" if "stack_short_nr" in dff.columns else None,
        hover_data=[c for c in ["j_set_plot", "result_date_local_ts", "u_cell_avg", "c_h2_ino2", "c_o2_inh2", "mf_h2", "p_an_diff", "t_an_diff", "setpoint_direction", "stack_short_nr"] if c in dff.columns],
    )
    fig3.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        title={"text": f"{pp} vs {x_param}", "x": 0.5, "pad": {"t": 8, "b": 0}},
        xaxis_title=f"{x_param}, current density in A/cm2",
        yaxis_title=pp,
        legend_title_text="Stack",
    )

    return fig1, fig2, fig3


@callback(
    Output("myc-polcurve-csv", "data"),
    Input("myc-polcurve-download", "n_clicks"),
    State("myc-polcurve-data-store", "data"),
    State("myc-polcurve-up", "value"),
    State("myc-polcurve-stack", "value"),
    State("myc-polcurve-setpoint", "value"),
    State("myc-polcurve-eol", "value"),
    prevent_initial_call=True,
)
def download_csv(n_clicks, raw, up, stack, setpoint, eol):
    if not n_clicks:
        return no_update
    df = _normalize_df(pd.DataFrame(raw or []))
    dff = _filter_df(df, up, stack, setpoint, eol)
    return send_data_frame(dff.to_csv, "mycroft_eol_polcurve.csv", index=False)
