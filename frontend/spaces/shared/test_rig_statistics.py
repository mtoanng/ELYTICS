from dash import dcc, callback, Output, Input, State, no_update, callback_context
import pandas as pd
import plotly.express as px
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from services.backend_service import get_table_as_df

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
    "Different years can be selected via the filter.",
    "Sample types or locations can be selected via filters or by clicking on the bars in the plots.",
    "Note: some testrigs do not show all data yet, as data is currently being ingested.",
]


def _normalize_statistics_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    normalized = df.copy()

    if "number_of_cells" in normalized.columns:
        normalized["number_of_cells"] = (
            normalized["number_of_cells"]
            .fillna("Unknown")
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
        )

    if "sample_type_state" in normalized.columns:
        normalized["sample_type_state"] = normalized["sample_type_state"].fillna("Unknown")

    return normalized


def create_test_rig_statistics_page(ns: str):
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
                                        id=f"{ns}-statistics-usage-toggle",
                                        variant="subtle",
                                        color="blue",
                                        size="md",
                                        radius="xl",
                                    ),
                                ],
                            ),
                            dmc.Text("Test rig statistics overview of running hours.", c="dimmed"),
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
                                id=f"{ns}-statistics-usage-collapse",
                                opened=False,
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
                                            id=f"{ns}-year-selector",
                                            multi=True,
                                            clearable=False,
                                            placeholder="Select year(s)",
                                            style={"width": "100%"},
                                        ),
                                        label="Year",
                                        htmlFor=f"{ns}-year-selector",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": 1, "minWidth": "180px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id=f"{ns}-location-filter",
                                            multi=True,
                                            placeholder="Select location(s)",
                                            style={"width": "100%"},
                                        ),
                                        label="Location",
                                        htmlFor=f"{ns}-location-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": 1, "minWidth": "180px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id=f"{ns}-sample-type-filter",
                                            multi=True,
                                            placeholder="Select sample type",
                                            style={"width": "100%"},
                                        ),
                                        label="Sample Type",
                                        htmlFor=f"{ns}-sample-type-filter",
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
                                            dmc.Paper(
                                                id=f"{ns}-active-selection-display",
                                                withBorder=True,
                                                p="xs",
                                                radius="sm",
                                                style={"minHeight": "44px"},
                                            ),
                                        ],
                                    ),
                                    dmc.Button(
                                        "Reset selection",
                                        id=f"{ns}-reset-selection-btn",
                                        n_clicks=0,
                                        variant="light",
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
                                children=dcc.Graph(id=f"{ns}-plot-hours-per-testrig", config={"responsive": True}),
                            ),
                            dmc.Paper(
                                withBorder=True,
                                p="xs",
                                radius="md",
                                children=dcc.Graph(id=f"{ns}-plot-cumulative-location", config={"responsive": True}),
                            ),
                            dmc.Paper(
                                withBorder=True,
                                p="xs",
                                radius="md",
                                children=dcc.Graph(id=f"{ns}-plot-sampletype-by-cells", config={"responsive": True}),
                            ),
                            dmc.Paper(
                                withBorder=True,
                                p="xs",
                                radius="md",
                                children=dcc.Graph(id=f"{ns}-plot-cells-by-sampletype", config={"responsive": True}),
                            ),
                        ],
                    ),
                    dcc.Store(id=f"{ns}-testrig-store"),
                    dcc.Store(
                        id=f"{ns}-selected-bars-store",
                        data={
                            "testrig_id": [],
                            "location": [],
                            "sample_type_state": [],
                            "number_of_cells": [],
                        },
                    ),
                    dcc.Store(id=f"{ns}-teststat-raw-store"),
                    dcc.Store(id=f"{ns}-statistics-usage-open", data=False),
                ],
            )
        ],
    )

    @callback(
        Output(f"{ns}-statistics-usage-open", "data"),
        Input(f"{ns}-statistics-usage-toggle", "n_clicks"),
        State(f"{ns}-statistics-usage-open", "data"),
        prevent_initial_call=True,
    )
    def toggle_usage_blockquote(n_clicks, is_open):
        if n_clicks is None:
            return no_update
        return not bool(is_open)

    @callback(
        Output(f"{ns}-statistics-usage-collapse", "opened"),
        Input(f"{ns}-statistics-usage-open", "data"),
    )
    def sync_usage_blockquote(is_open):
        return bool(is_open)

    @callback(
        Output(f"{ns}-teststat-raw-store", "data"),
        Output(f"{ns}-year-selector", "options"),
        Output(f"{ns}-year-selector", "value"),
        Input(f"{ns}-year-selector", "id"),
        prevent_initial_call=False,
    )
    def init_teststat_data(_):
        df = _normalize_statistics_df(get_table_as_df("sherlock", "testrig_statistics"))

        years = sorted(
            pd.to_numeric(df["year"], errors="coerce")
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        )
        options = [{"label": str(y), "value": y} for y in years]

        return df.to_dict("records"), options, years

    @callback(
        Output(f"{ns}-testrig-store", "data"),
        Output(f"{ns}-location-filter", "options"),
        Output(f"{ns}-sample-type-filter", "options"),
        Input(f"{ns}-teststat-raw-store", "data"),
        Input(f"{ns}-year-selector", "value"),
    )
    def load_data(raw_data, years):
        if not raw_data:
            return [], [], []

        df = _normalize_statistics_df(pd.DataFrame(raw_data))

        if years:
            df = df[df["year"].isin(years)]

        locations = sorted(df["location"].dropna().unique())
        sample_types = sorted(df["sample_type_state"].dropna().unique())

        location_options = [{"label": l, "value": l} for l in locations]
        sample_type_options = [{"label": s, "value": s} for s in sample_types]

        return df.to_dict("records"), location_options, sample_type_options

    @callback(
        Output(f"{ns}-selected-bars-store", "data"),
        Input(f"{ns}-plot-hours-per-testrig", "clickData"),
        Input(f"{ns}-plot-cumulative-location", "clickData"),
        Input(f"{ns}-plot-sampletype-by-cells", "clickData"),
        Input(f"{ns}-plot-cells-by-sampletype", "clickData"),
        Input(f"{ns}-reset-selection-btn", "n_clicks"),
        State(f"{ns}-selected-bars-store", "data"),
        prevent_initial_call=True,
    )
    def update_selected_bars(fig1, fig2, fig3, fig4, reset, selected):
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger == f"{ns}-reset-selection-btn":
            return {
                "testrig_id": [],
                "location": [],
                "sample_type_state": [],
                "number_of_cells": [],
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

        if trigger == f"{ns}-plot-hours-per-testrig":
            selected["testrig_id"] = toggle(selected["testrig_id"], point["x"])
        elif trigger == f"{ns}-plot-cumulative-location":
            selected["location"] = toggle(selected["location"], point["x"])
        elif trigger == f"{ns}-plot-sampletype-by-cells":
            selected["sample_type_state"] = toggle(selected["sample_type_state"], point["x"])
        elif trigger == f"{ns}-plot-cells-by-sampletype":
            selected["number_of_cells"] = toggle(selected["number_of_cells"], str(point["x"]))
        return selected

    @callback(
        Output(f"{ns}-location-filter", "value"),
        Output(f"{ns}-sample-type-filter", "value"),
        Input(f"{ns}-reset-selection-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_filters(_):
        return [], []

    @callback(
        Output(f"{ns}-active-selection-display", "children"),
        Output(f"{ns}-reset-selection-btn", "style"),
        Input(f"{ns}-selected-bars-store", "data"),
    )
    def update_selection_display_and_button_style(selected):
        parts = []
        if selected["testrig_id"]:
            parts.append(f"Test rigs: {', '.join(selected['testrig_id'])}")
        if selected["location"]:
            parts.append(f"Locations: {', '.join(selected['location'])}")
        if selected["sample_type_state"]:
            parts.append(f"Sample types: {', '.join(selected['sample_type_state'])}")
        if selected["number_of_cells"]:
            parts.append(f"Cells: {', '.join(selected['number_of_cells'])}")

        has_selection = bool(parts)
        button_style = {
            "flex": "0 0 auto",
            "whiteSpace": "nowrap",
            "height": "44px",
            "alignSelf": "flex-end",
            "opacity": 1 if has_selection else 0.7,
        }

        if not parts:
            return dmc.Text("No selections", size="sm", c="dimmed"), button_style

        return (
            dmc.Group(
                gap="xs",
                wrap="wrap",
                children=[
                    dmc.Badge(item, variant="light", radius="xl", size="md")
                    for item in parts
                ],
            ),
            button_style,
        )

    @callback(
        Output(f"{ns}-plot-hours-per-testrig", "figure"),
        Output(f"{ns}-plot-cumulative-location", "figure"),
        Output(f"{ns}-plot-sampletype-by-cells", "figure"),
        Output(f"{ns}-plot-cells-by-sampletype", "figure"),
        Input(f"{ns}-testrig-store", "data"),
        Input(f"{ns}-selected-bars-store", "data"),
        Input(f"{ns}-year-selector", "value"),
        Input(f"{ns}-location-filter", "value"),
        Input(f"{ns}-sample-type-filter", "value"),
        Input("theme-store", "data"),
    )
    def update_charts(data, selected, years, locations, sample_types, theme):
        fig_height = 420
        legend_layout = dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            entrywidth=110,
            entrywidthmode="pixels",
        )

        dff = _normalize_statistics_df(pd.DataFrame(data))
        if "run_hours" in dff.columns:
            dff["run_hours"] = pd.to_numeric(dff["run_hours"], errors="coerce").fillna(0)
        if "year" in dff.columns:
            dff["year_numeric"] = pd.to_numeric(dff["year"], errors="coerce")

        if locations:
            dff = dff[dff["location"].isin(locations)]
        if sample_types:
            dff = dff[dff["sample_type_state"].isin(sample_types)]
        if years:
            if "year_numeric" in dff.columns:
                dff = dff[dff["year_numeric"].isin(years)]
            else:
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

        fig1_data = (
            dff.groupby(["testrig_id", "location"], as_index=False)
            .agg(run_hours=("run_hours", "sum"))
            .sort_values(["location", "run_hours"], ascending=[True, False])
        )
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
            xaxis={"categoryorder": "array", "categoryarray": testrig_order},
            xaxis_title="Test Rig ID",
            yaxis_title="Run Hours",
            margin=dict(l=40, r=20, t=40, b=40),
            title=dict(text="Run Hours per Testrig ID per Location", y=0.96, yanchor="top", pad=dict(t=0)),
        )

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
            xaxis={"categoryorder": "array", "categoryarray": fig2_data["location"].tolist()},
            xaxis_title="Location",
            yaxis_title="Run Hours",
            margin=dict(l=40, r=20, t=40, b=40),
            title=dict(text="Cumulative Run Hours per Location", y=0.96, yanchor="top", pad=dict(t=0)),
        )

        fig3_data = dff.groupby(["sample_type_state", "number_of_cells"], as_index=False)["run_hours"].sum()
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
            xaxis={"categoryorder": "array", "categoryarray": sample_order},
            xaxis_title="Sample Type",
            yaxis_title="Run Hours",
            margin=dict(l=40, r=20, t=40, b=40),
        )

        cell_order = dff["number_of_cells"].unique().tolist()
        numeric_cells = sorted([c for c in cell_order if c.isdigit()], key=int)
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
            xaxis={"categoryorder": "array", "categoryarray": numeric_cells},
            margin=dict(l=40, r=20, t=40, b=40),
        )

        for fig in (fig1, fig2, fig3, fig4):
            fig.update_layout(
                height=fig_height,
                margin=dict(l=48, r=120, t=48, b=48),
                legend=legend_layout,
                legend_title_text=None,
            )
            fig.update_traces(
                selected={"marker": {"opacity": 1}},
                unselected={"marker": {"opacity": 0.2}},
            )

        return fig1, fig2, fig3, fig4

    return layout
