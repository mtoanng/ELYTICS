import dash
from dash import html, dcc, callback, Output, Input, State, register_page, no_update, callback_context
import pandas as pd
import plotly.express as px
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from services.backend_service import get_table_as_df

register_page(
    __name__,
    path="/sherlock/management/test-rig-statistics",
    name="HOLMES - Sherlock - Test Rig Statistics"
)

CELL_COLORS = {
    "1": "#5DADE2",
    "5": "#48C9B0",
    "6": "#F5B041",
    "14": "#AF7AC5",
    "25": "#DC3912",
    "65": "#F1948A",
    "160": "#AAB7B8",
    "Unknown": "#D5DBDB",
}

LOCATION_COLORS = {
    "TbP": "#54A24B",
    "RnG": "#C0392B",
    "BaP": "#2E86C1",
    "Liz": "#F79400",
    "External": "#7D3C98",
}

SAMPLE_TYPE_COLORS = {
    "Subscale": "rgb(252, 141, 98)",
    "Gen 2": "#5B6DCD",
    "Gen 1": "#F4D03F",
    "RnD": "#AF601A",
    "Unknown": "rgb(102, 102, 102)",
    "Other": "#9D755D",
}

USAGE_BLOCKQUOTE_TEXT = [
    "Only electrochemical testing is shown.",
    "Note: some testrigs do not show all data yet, as data is currently being ingested."
]

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
                                dmc.Title("ELY Test rig Dashboard", order=2),
                                dmc.ActionIcon(
                                    DashIconify(icon="material-symbols:info-outline", width=20),
                                    id="statistics-usage-toggle",
                                    variant="subtle",
                                    color="blue",
                                    size="md",
                                    radius="xl",
                                ),
                            ],
                        ),
                        dmc.Text("This page provides an overview of test rig statistics.", c="dimmed"),
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
                            id="statistics-usage-collapse",
                        ),
                    ],
                ),

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
                                        id="year-selector",
                                        multi=True,
                                        clearable=False,
                                        placeholder="Select year(s)",
                                        style={"width": "100%"},
                                    ),
                                    label="Year",
                                    htmlFor="year-selector",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "180px"},
                                ),
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="location-filter",
                                        multi=True,
                                        placeholder="Select location(s)",
                                        style={"width": "100%"},
                                    ),
                                    label="Location",
                                    htmlFor="location-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "180px"},
                                ),
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="sample-type-filter",
                                        multi=True,
                                        placeholder="Select sample type",
                                        style={"width": "100%"},
                                    ),
                                    label="Sample Type",
                                    htmlFor="sample-type-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "180px"},
                                ),
                            ],
                        ),
                        dmc.Space(h="sm"),
                        dmc.Group(
                            align="flex-start",
                            justify="space-between",
                            wrap="nowrap",
                            children=[
                                dmc.Stack(
                                    gap=6,
                                    style={"flex": 1},
                                    children=[
                                        dmc.Text("Selection(s) via plot", fw=600, size="sm"),
                                        html.Div(
                                            id="active-selection-display",
                                            style={
                                                "padding": "6px 10px",
                                                "border": "1px solid #c7d4f3",
                                                "borderRadius": "6px",
                                                "background": "#eef4ff",
                                                "fontSize": "13px",
                                                "minHeight": "44px",
                                                "whiteSpace": "normal",
                                                "display": "flex",
                                                "flexDirection": "row",
                                                "gap": "6px",
                                                "flexWrap": "wrap",
                                                "alignItems": "center",
                                            },
                                        ),
                                    ],
                                ),
                                dmc.Button(
                                    "Reset selection",
                                    id="reset-selection-btn",
                                    n_clicks=0,
                                    variant="light",
                                    color="gray",
                                    radius="md",
                                    style={
                                        "flex": "0 0 auto",
                                        "whiteSpace": "nowrap",
                                        "height": "44px",
                                        "alignSelf": "flex-end",
                                    },
                                ),
                            ],
                        ),
                    ],
                ),

                dmc.SimpleGrid(
                    cols=2,
                    spacing="md",
                    verticalSpacing="md",
                    children=[
                        dmc.Paper(
                            withBorder=True,
                            p="xs",
                            radius="md",
                            children=dcc.Graph(id="plot-hours-per-testrig", config={"responsive": True}),
                        ),
                        dmc.Paper(
                            withBorder=True,
                            p="xs",
                            radius="md",
                            children=dcc.Graph(id="plot-cumulative-location", config={"responsive": True}),
                        ),
                        dmc.Paper(
                            withBorder=True,
                            p="xs",
                            radius="md",
                            children=dcc.Graph(id="plot-sampletype-by-cells", config={"responsive": True}),
                        ),
                        dmc.Paper(
                            withBorder=True,
                            p="xs",
                            radius="md",
                            children=dcc.Graph(id="plot-cells-by-sampletype", config={"responsive": True}),
                        ),
                    ],
                ),

                dcc.Store(id="testrig-store"),
                dcc.Store(
                    id="selected-bars-store",
                    data={
                        "testrig_id": [],
                        "location": [],
                        "sample_type_state": [],
                        "number_of_cells": [],
                    },
                ),
                dcc.Store(id="teststat-raw-store"),
                dcc.Store(id="statistics-usage-open", data=True)
            ],
        )
    ],
)

# =========================================================
# INFO PANEL COLLAPSE
# =========================================================
@callback(
    Output("statistics-usage-open", "data"),
    Input("statistics-usage-toggle", "n_clicks"),
    State("statistics-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage_blockquote(n_clicks, is_open):
    if n_clicks is None:
        return no_update
    return not bool(is_open)

@callback(
    Output("statistics-usage-collapse", "opened"),
    Input("statistics-usage-open", "data"),
)
def sync_usage_blockquote(is_open):
    return bool(is_open)

# =========================================================
# POPULATE RAW DATA STORE & YEAR SELECTOR
# =========================================================
@callback(
    Output("teststat-raw-store", "data"),
    Output("year-selector", "options"),
    Output("year-selector", "value"),
    Input("year-selector", "id"),  # fires on initial render
    prevent_initial_call=False,
)
def init_teststat_data(_):
    df = get_table_as_df("sherlock", "test_statistics")
    df["number_of_cells"] = (
        df["number_of_cells"]
        .fillna("Unknown")
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
    )
    df["sample_type_state"] = df["sample_type_state"].fillna("Unknown")

    years = sorted(
        pd.to_numeric(df["year"], errors="coerce")
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )
    options = [{"label": str(y), "value": y} for y in years]

    return df.to_dict("records"), options, years

# =========================================================
# MULTI-SELECTION HANDLER
# =========================================================
@callback(
    Output("testrig-store", "data"),
    Output("location-filter", "options"),
    Output("sample-type-filter", "options"),
    Input("teststat-raw-store", "data"),
    Input("year-selector", "value"),
)
def load_data(raw_data, years):
    if not raw_data:
        return [], [], []

    df = pd.DataFrame(raw_data)

    if years:
        df = df[df["year"].isin(years)]

    locations = sorted(df["location"].dropna().unique())
    sample_types = sorted(df["sample_type_state"].dropna().unique())

    location_options = [{"label": l, "value": l} for l in locations]
    sample_type_options = [{"label": s, "value": s} for s in sample_types]

    return df.to_dict("records"), location_options, sample_type_options

@callback(
    Output("selected-bars-store", "data"),
    Input("plot-hours-per-testrig", "clickData"),
    Input("plot-cumulative-location", "clickData"),
    Input("plot-sampletype-by-cells", "clickData"),
    Input("plot-cells-by-sampletype", "clickData"),
    Input("reset-selection-btn", "n_clicks"),
    State("selected-bars-store", "data"),
    prevent_initial_call=True
)
def update_selected_bars(fig1, fig2, fig3, fig4, reset, selected):
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"].split(".")[0]
    if trigger == "reset-selection-btn":
        return {
            "testrig_id": [],
            "location": [],
            "sample_type_state": [],
            "number_of_cells": []
        }
    clicked = ctx.triggered[0]["value"]
    if not clicked:
        return selected
    point = clicked["points"][0]
    def toggle(lst, value):
        if value in lst:
            lst.remove(value)
        else:
            lst.append(value)
        return lst
    if trigger == "plot-hours-per-testrig":
        selected["testrig_id"] = toggle(selected["testrig_id"], point["x"])
    elif trigger == "plot-cumulative-location":
        selected["location"] = toggle(selected["location"], point["x"])
    elif trigger == "plot-sampletype-by-cells":
        selected["sample_type_state"] = toggle(selected["sample_type_state"], point["x"])
    elif trigger == "plot-cells-by-sampletype":
        selected["number_of_cells"] = toggle(selected["number_of_cells"], str(point["x"]))
    return selected

# =========================================================
# RESET LOCATION DROPDOWN
# =========================================================
@callback(
    Output("location-filter", "value"),
    Output("sample-type-filter", "value"),
    Input("reset-selection-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(_):
    return [], []

# =========================================================
# ACTIVE SELECTION DISPLAY
# =========================================================
@callback(
    Output("active-selection-display", "children"),
    Input("selected-bars-store", "data")
)
def update_selection_display(selected):
    parts = []
    if selected["testrig_id"]:
        parts.append(f"🔵 Test rigs: {', '.join(selected['testrig_id'])}")
    if selected["location"]:
        parts.append(f"🟢 Locations: {', '.join(selected['location'])}")
    if selected["sample_type_state"]:
        parts.append(f"🟣 Sample types: {', '.join(selected['sample_type_state'])}")
    if selected["number_of_cells"]:
        parts.append(f"🟠 Cells: {', '.join(selected['number_of_cells'])}")

    if not parts:
        return html.Span("No selections", style={"color": "#6c757d"})

    return [
        html.Span(
            item,
            style={
                "display": "inline-flex",
                "alignItems": "center",
                "padding": "2px 8px",
                "borderRadius": "999px",
                "background": "#dfeaff",
                "border": "1px solid #c7d4f3",
            },
        )
        for item in parts
    ]

# =========================================================
# BUILD CHARTS
# =========================================================
@callback(
    Output("plot-hours-per-testrig", "figure"),
    Output("plot-cumulative-location", "figure"),
    Output("plot-sampletype-by-cells", "figure"),
    Output("plot-cells-by-sampletype", "figure"),
    Input("testrig-store", "data"),
    Input("selected-bars-store", "data"),
    Input("year-selector", "value"),
    Input("location-filter", "value"),
    Input("sample-type-filter", "value"),
    Input("theme-store", "data"),
)
def update_charts(data, selected, years, locations, sample_types, theme):
    FIG_HEIGHT = 420
    LEGEND_LAYOUT = dict(
        orientation="v",
        yanchor="top",
        y=1,
        xanchor="left",
        x=1.02,
        entrywidth=110,
        entrywidthmode="pixels",
    )
    dff = pd.DataFrame(data)
    dff["number_of_cells"] = (
        dff["number_of_cells"]
        .fillna("Unknown")
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
    )
    dff["sample_type_state"] = dff["sample_type_state"].fillna("Unknown")
    if locations:
        dff = dff[dff["location"].isin(locations)]
    if sample_types:
        dff = dff[dff["sample_type_state"].isin(sample_types)]
    if years:
        dff = dff[dff["year"].isin(years)]
    dff = dff[dff["run_hours"] > 0]
    if selected["testrig_id"]:
        dff = dff[dff["testrig_id"].isin(selected["testrig_id"])]
    if selected["location"]:
        dff = dff[dff["location"].isin(selected["location"])]
    if selected["sample_type_state"]:
        dff = dff[dff["sample_type_state"].isin(selected["sample_type_state"])]
    if selected["number_of_cells"]:
        dff = dff[dff["number_of_cells"].astype(str).isin(selected["number_of_cells"])]
    
    template = "plotly_dark" if theme == "dark" else "plotly"
    
    # -------------------------
    # FIG 1 — Run hours per testrig
    # -------------------------
   
    fig1_data = (
        dff.groupby(["testrig_id", "location"], as_index=False)
        .agg(run_hours=("run_hours", "sum"))
    )

    # sort within each location
    fig1_data = fig1_data.sort_values(
        ["location", "run_hours"],
        ascending=[True, False]
    )

    # preserve order on x-axis
    testrig_order = fig1_data["testrig_id"].tolist()

    fig1 = px.bar(
        fig1_data,
        x="testrig_id",
        y="run_hours",
        color="location",
        color_discrete_map=LOCATION_COLORS,
        title="Run Hours per Testrig ID per Location",
        template=template,
    )

    fig1.update_layout(
        xaxis={
            "categoryorder": "array",
            "categoryarray": testrig_order,
        }
    )

    fig1.update_layout(
        xaxis_title="Test Rig ID",
        yaxis_title="Run Hours",
    )

    # -------------------------
    # FIG 2 — Cumulative per location
    # -------------------------

    fig2_data = (
        dff.groupby("location", as_index=False)
        .agg(run_hours=("run_hours", "sum"))
        .sort_values("run_hours", ascending=False)
    )

    fig2 = px.bar(
        fig2_data,
        x="location",
        y="run_hours",
        color="location",
        color_discrete_map=LOCATION_COLORS,
        title="Cumulative Run Hours per Location",
        template=template,
    )

    fig2.update_layout(
        xaxis={
            "categoryorder": "array",
            "categoryarray": fig2_data["location"].tolist(),
        }
    )

    fig2.update_layout(
        xaxis_title="Location",
        yaxis_title="Run Hours",
    )

    # -------------------------
    # FIG 1 & FIG 2 — Top Row Margin
    # -------------------------

    TOP_ROW_MARGIN = dict(l=40, r=20, t=40, b=40)

    fig1.update_layout(
        margin=TOP_ROW_MARGIN,
        title=dict(
            text="Run Hours per Testrig ID per Location",
            y=0.96,
            yanchor="top",
            pad=dict(t=0),
        ),
    )

    fig2.update_layout(
        margin=TOP_ROW_MARGIN,
        title=dict(
            text="Cumulative Run Hours per Location",
            y=0.96,
            yanchor="top",
            pad=dict(t=0),
        ),
    )


    # -------------------------
    # FIG 3 — Sample type vs cells
    # -------------------------
    fig3_data = (
        dff.groupby(
            ["sample_type_state", "number_of_cells"],
            as_index=False
        )["run_hours"]
        .sum()
    )

    # total run hours per sample type
    sample_order = (
        fig3_data.groupby("sample_type_state")["run_hours"]
        .sum()
        .sort_values(ascending=False)
        .index
        .tolist()
    )

    fig3 = px.bar(
        fig3_data,
        x="sample_type_state",
        y="run_hours",
        color="number_of_cells",
        color_discrete_map=CELL_COLORS,
        title="Run Hours per Sample Type grouped by Number of Cells",
        template=template,
    )

    fig3.update_layout(
        xaxis={
            "categoryorder": "array",
            "categoryarray": sample_order,
        },
        xaxis_title="Sample Type",
        yaxis_title="Run Hours",
    )

    # -------------------------
    # FIG 4 — Cells vs sample type
    # -------------------------

    cell_order = (
        dff["number_of_cells"]
        .unique()
        .tolist()
    )

    numeric_cells = sorted(
        [c for c in cell_order if c.isdigit()],
        key=int
    )

    if "Unknown" in cell_order:
        numeric_cells.append("Unknown")

    fig4 = px.bar(
        dff.groupby(["number_of_cells", "sample_type_state"], as_index=False)["run_hours"].sum(),
        x="number_of_cells",
        y="run_hours",
        color="sample_type_state",
        color_discrete_map=SAMPLE_TYPE_COLORS,
        title="Run Hours per Number of Cells grouped by Sample Type",
        template=template,
    )

    fig4.update_layout(
        xaxis_title="Number of Cells",
        yaxis_title="Run Hours",
    )

    fig4.update_layout(
        xaxis={
            "categoryorder": "array",
            "categoryarray": numeric_cells,
        }
    )

    BOTTOM_ROW_MARGIN = dict(l=40, r=20, t=40, b=40)

    fig3.update_layout(margin=BOTTOM_ROW_MARGIN)
    fig4.update_layout(margin=BOTTOM_ROW_MARGIN)


    for fig in (fig1, fig2, fig3, fig4):
        fig.update_layout(
            height=FIG_HEIGHT,
            # margin=STANDARD_MARGIN,
            margin=dict(l=48, r=120, t=48, b=48),  # extra right space
            legend=LEGEND_LAYOUT,
            legend_title_text=None,
        )
        fig.update_traces(
            selected={"marker": {"opacity": 1}},
            unselected={"marker": {"opacity": 0.2}},
        )


    return fig1, fig2, fig3, fig4