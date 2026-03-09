import dash
from dash import html, dcc, callback, Output, Input, State, register_page, no_update, callback_context
import pandas as pd
import plotly.express as px

from services.backend_service import get_table_as_df

register_page(
    __name__,
    path="/sherlock/management/test-statistics",
    name="HOLMES - Sherlock - Test Statistics"
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

layout = html.Div(
    [
        html.H2("ELY Test rig Dashboard", style={"textAlign": "left", "marginTop": "0.5rem"}),
        html.H3("Only electrochemical testing is shown", style={"marginBottom": "12px"}),
        html.Div(
            [
                html.Div(
                    [
                        html.Div("Year Range", style={"fontWeight": "600", "marginBottom": "6px"}),
                        dcc.Checklist(
                            id="year-selector",
                            options=[
                                {"label": "2024", "value": 2024},
                                {"label": "2025", "value": 2025},
                                {"label": "2026", "value": 2026},
                            ],
                            value=[2024, 2025, 2026],
                            labelStyle={"display": "block", "marginBottom": "4px"},
                            inputStyle={"marginRight": "6px"},
                        ),
                        html.Hr(style={"margin": "12px 0"}),
                        html.Div("Location", style={"fontWeight": "600", "marginBottom": "6px"}),
                        dcc.Dropdown(
                            id="location-filter",
                            multi=True,
                            placeholder="Select location(s)",
                        ),
                        html.Div(
                            "Sample Type",
                            style={"fontWeight": "600", "marginBottom": "6px", "marginTop": "8px"},
                        ),
                        dcc.Dropdown(
                            id="sample-type-filter",
                            multi=True,
                            placeholder="Select sample type",
                        ),
                        html.Hr(style={"margin": "12px 0"}),
                        html.Div("Selection(s) via plot", style={"fontWeight": "600", "marginBottom": "6px"}),
                        html.Div(
                            id="active-selection-display",
                            style={
                                "padding": "6px 10px",
                                "border": "1px solid #c7d4f3",
                                "borderRadius": "6px",
                                "background": "#eef4ff",
                                "fontSize": "13px",
                                "minHeight": "32px",
                                "marginBottom": "6px",
                                "whiteSpace": "normal",
                                "display": "flex",
                                "flexDirection": "column",
                                "gap": "4px",
                            },
                        ),
                        html.Button(
                            "Reset selection",
                            id="reset-selection-btn",
                            n_clicks=0,
                            className="btn btn-secondary",
                            style={
                                "width": "100%",
                                "borderRadius": "6px",
                                "padding": "6px 12px",
                                "fontWeight": "600",
                                "fontSize": "14px",
                            },
                        ),
                    ],
                    style={
                        "width": "260px",
                        "padding": "12px",
                        "flexShrink": "0",
                    },
                ),
                html.Div(
                    [
                        dcc.Graph(id="plot-hours-per-testrig", config={"responsive": True}),
                        dcc.Graph(id="plot-cumulative-location", config={"responsive": True}),
                        dcc.Graph(id="plot-sampletype-by-cells", config={"responsive": True}),
                        dcc.Graph(id="plot-cells-by-sampletype", config={"responsive": True}),
                    ],
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "1fr 1fr",
                        "gap": "12px",
                        "flexGrow": "1",
                        "alignItems": "start",
                    },
                ),
            ],
            style={
                "display": "flex",
                "alignItems": "flex-start",
                "gap": "12px",
            },
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
    ]
)

@callback(
    Output("testrig-store", "data"),
    Output("location-filter", "options"),
    Output("sample-type-filter", "options"),
    Input("year-selector", "value"),
)
def load_data(years):
    df = get_table_as_df('sherlock', 'test_statistics')
    df["number_of_cells"] = (
        df["number_of_cells"]
        .fillna("Unknown")
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
    )
    df["sample_type_state"] = df["sample_type_state"].fillna("Unknown")
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

@callback(
    Output("location-filter", "value"),
    Output("sample-type-filter", "value"),
    Input("reset-selection-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(_):
    return [], []

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
        return html.Div("No selections", style={"color": "#6c757d"})
    return [html.Div(item) for item in parts]

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
        dff.groupby(
            ["testrig_id", "location"],
            as_index=False
        )["run_hours"]
        .sum()
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
        dff.groupby("location", as_index=False)["run_hours"]
        .sum()
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