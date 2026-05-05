from datetime import datetime
from dateutil.relativedelta import relativedelta

from dash import dcc, callback, Output, Input, State, register_page, no_update
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import plotly.express as px
import pandas as pd

from services.backend_service import get_tabular

register_page(
    __name__,
    path="/mycroft/management/production-overview",
    title="HOLMES - Mycroft - Production Overview",
)

USAGE_BLOCKQUOTE_TEXT = [
    "Use Number of Cells and Proto to focus the production cohort.",
    "Date range adjusts all charts and KPI cards together.",
    "Default range is the last 6 months.",
]


def _load_data() -> pd.DataFrame:
    try:
        df = get_tabular("mycroft", "production")
    except Exception:
        # Backward compatibility in case route is still named management.
        df = get_tabular("mycroft", "management")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def _make_options(series: pd.Series):
    vals = series.dropna().unique().tolist()
    try:
        vals = sorted(vals, key=lambda x: str(x))
    except Exception:
        pass
    return [{"label": str(v), "value": v} for v in vals]


def _option_values(options: list[dict]) -> list:
    return [option["value"] for option in options]


def _apply_common_filters(df: pd.DataFrame, cells, proto, date_start, date_end):
    dff = df.copy()
    if cells and "number_of_cells" in dff.columns:
        dff = dff[dff["number_of_cells"].isin(cells)]
    if proto and "proto" in dff.columns:
        dff = dff[dff["proto"].isin(proto)]

    today = datetime.now()
    default_start = today - relativedelta(months=6)
    start = pd.to_datetime(date_start, errors="coerce") if date_start else default_start
    end = pd.to_datetime(date_end, errors="coerce") if date_end else today

    if "date" in dff.columns:
        # Data loaded from dcc.Store may contain ISO date strings.
        # Coerce to datetime before range comparisons to avoid str-vs-datetime errors.
        dff["date"] = pd.to_datetime(dff["date"], errors="coerce")
        dff = dff[dff["date"] >= start]
        dff = dff[dff["date"] <= end]
    if "sq_asc" in dff.columns:
        dff = dff[dff["sq_asc"] == 1]
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
                                dmc.Title("Production Overview", order=2),
                                dmc.ActionIcon(
                                    DashIconify(icon="material-symbols:info-outline", width=20),
                                    id="myc-prod-usage-toggle",
                                    variant="subtle",
                                    color="blue",
                                    size="md",
                                    radius="xl",
                                ),
                            ],
                        ),
                        dmc.Text("Production split and monthly throughput overview.", c="dimmed"),
                        dmc.Collapse(
                            dmc.Blockquote(
                                dmc.List(withPadding=False, children=[dmc.ListItem(item) for item in USAGE_BLOCKQUOTE_TEXT]),
                                color="blue",
                            ),
                            id="myc-prod-usage-collapse",
                            opened=False,
                        ),
                    ],
                ),
                dcc.Store(id="myc-prod-usage-open", data=False),
                dcc.Store(id="myc-prod-data-store"),
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
                                dmc.InputWrapper(
                                    dcc.Dropdown(id="myc-prod-cells", multi=True, style={"width": "100%"}),
                                    label="Number of Cells",
                                    htmlFor="myc-prod-cells",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": "1", "minWidth": "180px"},
                                ),
                                dmc.InputWrapper(
                                    dcc.Dropdown(id="myc-prod-proto", multi=True, style={"width": "100%"}),
                                    label="Proto",
                                    htmlFor="myc-prod-proto",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": "1", "minWidth": "180px"},
                                ),
                                dmc.InputWrapper(
                                    dcc.DatePickerRange(
                                        id="myc-prod-date-range",
                                        display_format="YYYY-MM-DD",
                                        start_date=datetime.today() - relativedelta(months=6),
                                        end_date=datetime.today(),
                                    ),
                                    label="Date range",
                                    htmlFor="myc-prod-date-range",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": "1", "minWidth": "280px"},
                                ),
                            ],
                        ),
                    ],
                ),
                dmc.Box(
                    style={
                        "flex": "1 1 0",
                        "display": "grid",
                        "gridTemplateColumns": "minmax(260px, 0.9fr) minmax(0, 2.1fr)",
                        "gridTemplateRows": "auto auto minmax(0, 1fr)",
                        "gap": "16px",
                        "minHeight": 0,
                        "overflow": "hidden",
                    },
                    children=[
                        dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="md",
                            style={"gridColumn": "1", "gridRow": "1"},
                            children=[dmc.Text("Total P1 stacks", c="dimmed", size="sm"), dmc.Title(id="myc-prod-kpi-p1", order=2)],
                        ),
                        dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="md",
                            style={"gridColumn": "1", "gridRow": "2"},
                            children=[dmc.Text("Total P2 stacks", c="dimmed", size="sm"), dmc.Title(id="myc-prod-kpi-p2", order=2)],
                        ),
                        dmc.Paper(
                            withBorder=True,
                            p="xs",
                            radius="md",
                            style={"gridColumn": "1", "gridRow": "3", "height": "100%", "minHeight": 0, "display": "flex", "overflow": "hidden"},
                            children=dcc.Graph(id="myc-prod-pie", style={"height": "100%", "width": "100%", "flex": "1 1 auto", "minHeight": 0}),
                        ),
                        dmc.Paper(
                            withBorder=True,
                            p="xs",
                            radius="md",
                            style={"gridColumn": "2", "gridRow": "1 / span 3", "height": "100%", "minHeight": 0, "display": "flex", "overflow": "hidden"},
                            children=dcc.Graph(id="myc-prod-bar", style={"height": "100%", "width": "100%", "flex": "1 1 auto", "minHeight": 0}),
                        ),
                    ],
                ),
            ],
        )
    ],
)


@callback(Output("myc-prod-usage-open", "data"), Input("myc-prod-usage-toggle", "n_clicks"), State("myc-prod-usage-open", "data"), prevent_initial_call=True)
def toggle_usage(n, opened):
    if n is None:
        return no_update
    return not bool(opened)


@callback(Output("myc-prod-usage-collapse", "opened"), Input("myc-prod-usage-open", "data"))
def sync_usage(opened):
    return bool(opened)


@callback(
    Output("myc-prod-data-store", "data"),
    Output("myc-prod-cells", "options"),
    Output("myc-prod-cells", "value"),
    Output("myc-prod-proto", "options"),
    Output("myc-prod-proto", "value"),
    Input("myc-prod-cells", "id"),
    prevent_initial_call=False,
)
def init_data(_):
    df = _load_data()
    cell_options = _make_options(df["number_of_cells"]) if "number_of_cells" in df.columns else []
    proto_options = _make_options(df["proto"]) if "proto" in df.columns else []
    return (
        df.to_dict("records"),
        cell_options,
        _option_values(cell_options),
        proto_options,
        _option_values(proto_options),
    )


@callback(
    Output("myc-prod-pie", "figure"),
    Output("myc-prod-bar", "figure"),
    Output("myc-prod-kpi-p1", "children"),
    Output("myc-prod-kpi-p2", "children"),
    Input("myc-prod-data-store", "data"),
    Input("myc-prod-cells", "value"),
    Input("myc-prod-proto", "value"),
    Input("myc-prod-date-range", "start_date"),
    Input("myc-prod-date-range", "end_date"),
    Input("theme-store", "data"),
)
def update_outputs(raw, cells, proto, date_start, date_end, theme):
    template = "plotly_dark" if theme == "dark" else "plotly"
    df = pd.DataFrame(raw or [])
    dff = _apply_common_filters(df, cells, proto, date_start, date_end)

    if dff.empty:
        return px.pie(template=template), px.bar(template=template), "0", "0"

    pie_source = (
        dff["identifier"].value_counts().rename_axis("identifier").reset_index(name="count")
        if "identifier" in dff.columns
        else pd.DataFrame({"identifier": [], "count": []})
    )
    pie = px.pie(
        pie_source,
        names="identifier",
        values="count",
        hole=0.3,
        title="Percentage of stacks",
        template=template,
        category_orders={"identifier": ["P1, 5 cell", "P1, 25 cell", "P1, 160 cell", "P2, 5 cell", "P2, 25 cell", "P2, 160 cell"]},
    )
    pie.update_layout(margin=dict(t=36, b=16, l=16, r=16), title_font_size=20)

    bar = px.bar(template=template)
    if "date" in dff.columns and "number_of_cells" in dff.columns:
        dff = dff.copy()
        dff["month_start"] = dff["date"].dt.to_period("M").dt.to_timestamp()
        counts = dff[["month_start", "number_of_cells"]].value_counts().reset_index(name="count")
        counts["month_name"] = counts["month_start"].dt.strftime("%Y-%m")
        counts["number_of_cells"] = counts["number_of_cells"].astype("string")
        month_order = sorted(counts["month_name"].unique())
        counts["month_name"] = pd.Categorical(counts["month_name"], categories=month_order, ordered=True)

        bar = px.bar(
            counts,
            x="month_name",
            y="count",
            text_auto=".1s",
            color="number_of_cells",
            barmode="group",
            title="Count of stacks per month",
            template=template,
            labels={"month_name": "Month", "count": "Stack count", "number_of_cells": "Number of cells"},
            category_orders={"number_of_cells": ["5", "25", "160"]},
        )
        bar.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
        bar.update_layout(title_font_size=20, margin=dict(t=36, b=24, l=16, r=16))
        bar.update_xaxes(tickmode="array", tickvals=month_order, ticktext=month_order, tickangle=-45, automargin=True)

    p1 = str(len(dff[dff["proto"] == "P1"])) if "proto" in dff.columns else "0"
    p2 = str(len(dff[dff["proto"] == "P2"])) if "proto" in dff.columns else "0"
    return pie, bar, p1, p2
