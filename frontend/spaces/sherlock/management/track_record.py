from dash import (
    html,
    dcc,
    callback,
    Output,
    Input,
    State,
    register_page,
    no_update,
)
from dash import callback_context as ctx
import dash_mantine_components as dmc
import dash_ag_grid as dag
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify
import plotly.graph_objects as go
import pandas as pd
import copy
from pathlib import Path
from typing import Any
from typing import Dict, Optional, List


register_page(__name__, path="/sherlock/management/track-record", title="HOLMES - Sherlock - Track Record")


# --------------------------- TEMP LOADING LOCAL DATA
# Absolute path to this file
here = Path(__file__).resolve()

# project_root is the directory that contains both 'frontend' and 'dummydata'
# management -> sherlock -> spaces -> frontend -> project_root
project_root = here.parents[4]

csv_path = project_root / "dummydata" / "Sherlock_track_record.csv"

if not csv_path.exists():
    raise FileNotFoundError(f"CSV not found at: {csv_path}")

df_track = pd.read_csv(csv_path)

# ---------------------------------------------------

# =========================================================
# LOAD DATA
# =========================================================

df_runtime = df_track[df_track["block"] == "RUNTIME_RANKING"].copy()
df_ts = df_track[df_track["block"] == "TIMESERIES"].copy()
df_table = df_track[df_track["block"] == "SAMPLE_TABLE"].copy()

# =========================================================
# AGGREGATION (SINGLE SOURCE OF TRUTH)
# =========================================================
df_runtime_agg = (
    df_runtime
    .drop_duplicates(subset=["sample_name"])
    .copy()
)

df_runtime_agg["total_run_hours"] = df_runtime_agg["run_hours"]

df_runtime_agg = df_runtime_agg.sort_values(
    "total_run_hours", ascending=False
)

df_table = df_table.merge(
    df_runtime_agg[["sample_name", "total_run_hours"]],
    on="sample_name",
    how="left",
)
df_table["total_run_hours"] = df_table["total_run_hours"].fillna(0)

SAMPLES = df_runtime_agg["sample_name"].tolist()


# =========================================================
# FILTER DEFAULTS (TIMESERIES)
# =========================================================

def _safe_min_max(series, fallback_min=0.0, fallback_max=0.0):
    clean = series.dropna()
    if clean.empty:
        return float(fallback_min), float(fallback_max)
    return float(clean.min()), float(clean.max())


def _clamp(value, min_val, max_val):
    return max(min_val, min(value, max_val))


JSTCK_MIN = 0.0
JSTCK_MAX = 3.0

tande_min_raw, tande_max_raw = _safe_min_max(df_ts["tAndeOut"], 0.0, 100.0)
pctde_min_raw, pctde_max_raw = _safe_min_max(df_ts["pCtdeOut"], 0.0, 100.0)

tande_min = round(tande_min_raw, 1)
tande_max = round(tande_max_raw, 1)
pctde_min = round(pctde_min_raw, 1)
pctde_max = round(pctde_max_raw, 1)

# JSTCK_DEFAULT = 3.0
# TANDE_DEFAULT = _clamp(70.0, tande_min, tande_max)
# PCTDE_DEFAULT = _clamp(40.0, pctde_min, pctde_max)

# DEFAULT_FILTERS = {
#     "jStck": JSTCK_DEFAULT,
#     "tAndeOut": TANDE_DEFAULT,
#     "pCtdeOut": PCTDE_DEFAULT,
# }


# =========================================================
# KPI CHART DATA (Gen 1 Proto 1 & Proto 2 only)
# =========================================================
df_kpi = df_track.copy()

# Keep only Gen 1 Proto 1 & Proto 2
df_kpi = df_kpi[
    df_kpi["sample_type_state"].isin(
        ["Gen 1 - Proto 1", "Gen 1 - Proto 2"]
    )
]

df_kpi = df_kpi[df_kpi["run_hours"] > 0]

df_kpi["number_of_cells"] = (
    df_kpi["number_of_cells"]
    .fillna("Unknown")
    .astype(str)
)

df_kpi_stack_level = (
    df_kpi
    .groupby(
        ["sample_name", "sample_type_state", "number_of_cells"],
        as_index=False
    )["run_hours"]
    .max()     # <-- we use max(), NOT sum() because there are multiple order ids for the same sample name
)

df_kpi_grouped = (
    df_kpi_stack_level
    .groupby(
        ["sample_type_state", "number_of_cells"],
        as_index=False
    )["run_hours"]
    .sum()
)


# =========================================================
# COLOR MAP
# =========================================================

palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
color_map = {
    name: palette[i % len(palette)]
    for i, name in enumerate(df_runtime_agg["sample_name"])
}


# =========================================================
# CONSTANTS
# =========================================================

USAGE_BLOCKQUOTE_TEXT = [
    "The top bar charts show total operational runtime per Gen 1 stack and sample types"
    "Hover on a bar to see detailed stack information"
    "All stacks are shown by default in the timeseries section",
    "Click on legend items to hide or show specific Gen 1 stacks",
    "Double-click a legend item to isolate that stack (all others will be hidden)",
    "Zoom in on one chart and the others will synchronize automatically",
    "Double-click inside any subplot to reset the zoom",
    "By default, all data is displayed without any filtering",
    "Select target values for jStck, tAndeOut, and/or pCtdeOut using the sliders or value boxes",
    "You can filter by one, two, or all three parameters",
    "Click 'Apply' to filter the data based on your selected values",
    "Data is filtered to show points within ±0.2 A/cm² for jStck, ±3°C for temp, ±5 bar for pressure",
    "Click 'Reset' to clear all filters, reset zoom, and return to viewing all data",
]

# =========================================================
# BAR CHART (STATIC)
# =========================================================

fig_runtime = go.Figure(
    go.Bar(
        x=df_runtime_agg["sample_name"],
        y=df_runtime_agg["total_run_hours"],
        marker_color=[color_map[s] for s in df_runtime_agg["sample_name"]],
        customdata=df_runtime_agg[
            [
                "sample_type",
                "sample_state",
                "production_plant",
                "ccm_name",
                "ptl_name",
                "gdl_name",
                "active_area_per_cell",
                "order_id",
                "leepa_number",
            ]
        ],
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Total runtime: %{y:.0f} h<br><br>"
            "Type / State: %{customdata[0]} - %{customdata[1]}<br>"
            "Plant: %{customdata[2]}<br>"
            "CCM: %{customdata[3]}<br>"
            "PTL: %{customdata[4]}<br>"
            "GDL: %{customdata[5]}<br>"
            "Active area / cell: %{customdata[6]}<br>"
            # "Order ID: %{customdata[7]}<br>"
            "Leepa number: %{customdata[8]}"
            "<extra></extra>"
        ),
    )
)

fig_runtime.update_layout(
    title="Top Gen 1 Stacks by Total Operational Runtime",
    xaxis_title="Stack (Sample name)",
    yaxis_title="Operational runtime [h]",
)
fig_runtime.update_xaxes(
    categoryorder="array",
    categoryarray=df_runtime_agg["sample_name"],
)

fig_runtime.update_layout(
    margin=dict(l=40, r=20, t=40, b=40),
)


# =========================================================
# KPI FIGURE (Left Top Subplot)
# =========================================================
df_kpi_grouped["number_of_cells"] = (
    df_kpi_grouped["number_of_cells"]
    .fillna("Unknown")
    .astype(str)
)

fig_kpi = go.Figure()

cell_values = sorted(df_kpi_grouped["number_of_cells"].unique())

for cell in cell_values:
    df_cell = df_kpi_grouped[
        df_kpi_grouped["number_of_cells"] == cell
    ]

    fig_kpi.add_trace(
        go.Bar(
            x=df_cell["sample_type_state"],
            y=df_cell["run_hours"],
            name=str(cell),
        )
    )

fig_kpi.update_layout(
    title="Run Hours per Sample Type grouped by Number of Cells",
    xaxis_title="Sample Type",
    yaxis_title="Run Hours",
    barmode="stack",
    legend_title_text="Number of Cells",
    margin=dict(l=40, r=20, t=40, b=40),
)


# =========================================================
# TIMESERIES FIGURE BUILDER
# =========================================================

def filter_timeseries(df, filters):
    if not filters:
        return df

    j_val = filters.get("jStck")
    t_val = filters.get("tAndeOut")
    p_val = filters.get("pCtdeOut")

    # Start with all rows
    mask = df.index.isin(df.index)  # True for all rows

    # Apply range filtering with updated tolerances: ±0.2 for jStck, ±3 for temp, ±5 for pressure
    if j_val is not None:
        mask = mask & (df["jStck"] >= j_val - 0.2) & (df["jStck"] <= j_val + 0.2)
    
    if t_val is not None:
        mask = mask & (df["tAndeOut"] >= t_val - 3.0) & (df["tAndeOut"] <= t_val + 3.0)
    
    if p_val is not None:
        mask = mask & (df["pCtdeOut"] >= p_val - 5.0) & (df["pCtdeOut"] <= p_val + 5.0)

    return df[mask]


def make_ts_fig(
    df_ts_input,
    y_col,
    title,
    y_label,
    visible_state,
    x_range,
    reset,
    y_range=None,
    y_reset=False,
):

    hidden = set(visible_state["hidden"]) if visible_state else set()
    fig = go.Figure()

    for i, sample in enumerate(SAMPLES):
        ts = df_ts_input[df_ts_input["sample_name"] == sample]

        fig.add_trace(
            go.Scatter(
                x=ts["runtime_hour"],
                y=ts[y_col],
                mode="markers",
                name=sample,
                visible="legendonly" if i in hidden else True,
                uirevision="shared-legend",
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Runtime [h]",
        yaxis_title=y_label,
        hovermode="x unified",
        uirevision="shared-zoom",
        showlegend=True,
        legend=dict(traceorder="normal", visible=True, title_text="Stack (Sample Name)"),
        margin=dict(l=40, r=20, t=40, b=40),
    )

    # Add threshold lines for H2 in O2 concentration only
    if y_col == "concH2O2":
        fig.add_hline(
            y=0.5,
            line_dash="dash",
            line_color="orange",
            annotation_text="  BoL: 0.5%",
            annotation_position="right",
        )
        fig.add_hline(
            y=0.8,
            line_dash="dash",
            line_color="red",
            annotation_text="  EoL: 0.8%",
            annotation_position="right",
        )

    if x_range:
        fig.update_xaxes(range=x_range)
    elif reset:
        fig.update_xaxes(autorange=True)

    if y_range:
        fig.update_yaxes(range=y_range)
    elif y_reset:
        fig.update_yaxes(autorange=True)

    return fig


# Show all data by default (no filtering)
df_ts_default = df_ts.copy()

# =========================================================
# LAYOUT
# =========================================================

info_tooltip = dmc.Tooltip(
    label=dmc.Text(
        "Filter Instructions:\n\n"
        "Default Behavior:\n"
        "• By default, all data is displayed without any filtering\n"
        "• Filter fields start empty - you choose what to filter by\n\n"
        "How to Apply Filters:\n"
        "1. Select target value(s) for one or more parameters:\n"
        "   - jStck (Current Density) [A/cm²]\n"
        "   - tAndeOut (Temperature) [°C]\n"
        "   - pCtdeOut (Pressure) [bar]\n"
        "2. Click 'Apply' to filter the data\n\n"
        "Filter Tolerances:\n"
        "• jStck: ±0.2 A/cm² tolerance\n"
        "• tAndeOut: ±3°C tolerance\n"
        "• pCtdeOut: ±5 bar tolerance\n\n"
        "Reset:\n"
        "• Click 'Reset' to clear all filters, reset zoom, and view all data again",
        size="sm",
        style={"whiteSpace": "pre-line"},
    ),
    withArrow=True,
    position="bottom",
    children=dmc.ActionIcon(
        DashIconify(icon="mdi:information-outline", width=18, height=18),
        variant="subtle",
    ),
)


def track_record_layout():
    return dmc.Container(
        size="xl",
        py="md",
        children=[
            dmc.Stack(
                gap="md",
                children=[
                    # Header + usage help
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
                                        id="trackrecord-usage-toggle",
                                        variant="subtle",
                                        color="blue",
                                        size="md",
                                        radius="xl",
                                    ),
                                ],
                            ),
                            dmc.Text(
                                "Top performing Gen 1 stacks based on total operational runtime (based on cloud data)",
                                c="dimmed",
                            ),
                            # Use in_ instead of opened for dmc.Collapse v2.6.0
                            dmc.Collapse(
                                id="trackrecord-usage-collapse",
                                opened=False,
                                children=dmc.Blockquote(
                                    dmc.List(
                                        withPadding=False,
                                        children=[dmc.ListItem(item) for item in USAGE_BLOCKQUOTE_TEXT],
                                    ),
                                    color="blue",
                                ),
                            ),
                        ],
                    ),

                    dcc.Store(id="trackrecord-usage-open", data=False),

                    dmc.Stack(
                        gap="md",
                        style={"width": "100%"},
                        children=[
                            # Main graphs grouped in a Paper
                            dmc.Paper(
                                withBorder=True,
                                p="md",
                                radius="md",
                                children=[
                                    dmc.SimpleGrid(
                                        cols=2,
                                        spacing="md",
                                        children=[
                                            dcc.Graph(
                                                id="runtime-kpi",
                                                figure=fig_kpi,
                                                config={"responsive": True},
                                                style={"width": "100%", "height": "420px"},
                                            ),
                                            dcc.Graph(
                                                id="runtime-bar",
                                                figure=fig_runtime,
                                                config={"responsive": True},
                                                style={"width": "100%", "height": "420px"},
                                            ),
                                        ],
                                    )
                                ],
                            ),

                            # COLLAPSIBLE HEADER
                            dmc.Paper(
                                dmc.Group(
                                    [
                                        dmc.Text(
                                            "Performance of the top 5 stacks (based on runtime)",
                                            fw=600,
                                            size="lg",
                                        ),
                                        dmc.ActionIcon(
                                            DashIconify(icon="bi:chevron-down", width=18, height=18, id="perf-chevron-icon"),
                                            id="perf-collapse-toggle",
                                            variant="subtle",
                                            size="lg",
                                        )
                                    ],
                                    align="center",
                                    gap="sm",
                                    style={"width": "100%"},
                                ),
                                withBorder=True,
                                radius="md",
                                p="md",
                                style={"width": "100%"},
                            ),

                            # TIMESERIES SECTION (STACKED) - COLLAPSIBLE
                            dmc.Collapse(
                                id="perf-collapse",
                                opened=False,
                                children=[
                                    dmc.Paper(
                                        [
                                            # Horizontal filter controls
                                            dmc.Group(
                                                        [
                                                            # Current Density filter
                                                            dmc.Stack(
                                                                [
                                                                    dmc.Text("Current Density (jStck) [A/cm²]", size="sm"),
                                                                    dmc.Group(
                                                                        [
                                                                            dmc.NumberInput(
                                                                                id="filter-jstck-input",
                                                                                step=0.1,
                                                                                value=None,
                                                                                placeholder="A/cm²",
                                                                                min=JSTCK_MIN,
                                                                                max=JSTCK_MAX,
                                                                                styles={"input": {"height": 28, "width": 68}},
                                                                            ),
                                                                            dmc.Slider(
                                                                                id="filter-jstck",
                                                                                min=JSTCK_MIN,
                                                                                max=JSTCK_MAX,
                                                                                step=0.1,
                                                                                value=None,
                                                                                marks=[],
                                                                                label=None,
                                                                                style={"width": 120, "marginLeft": 4, "marginRight": 4},
                                                                            ),
                                                                        ],
                                                                        gap="xs",
                                                                    ),
                                                                ],
                                                                gap="xs",
                                                            ),
                                                            # Temperature filter
                                                            dmc.Stack(
                                                                [
                                                                    dmc.Text("Temp (tAndeOut) [°C]", size="sm"),
                                                                    dmc.Group(
                                                                        [
                                                                            dmc.NumberInput(
                                                                                id="filter-tandeout-input",
                                                                                step=1,
                                                                                value=None,
                                                                                placeholder="°C",
                                                                                min=tande_min,
                                                                                max=tande_max,
                                                                                styles={"input": {"height": 28, "width": 68}},
                                                                            ),
                                                                            dmc.Slider(
                                                                                id="filter-tandeout",
                                                                                min=tande_min,
                                                                                max=tande_max,
                                                                                step=1,
                                                                                value=None,
                                                                                marks=[],
                                                                                label=None,
                                                                                style={"width": 120, "marginLeft": 4, "marginRight": 4},
                                                                            ),
                                                                        ],
                                                                        gap="xs",
                                                                    ),
                                                                ],
                                                                gap="xs",
                                                            ),
                                                            # Pressure filter
                                                            dmc.Stack(
                                                                [
                                                                    dmc.Text("Pressure (pCtdeOut) [bar]", size="sm"),
                                                                    dmc.Group(
                                                                        [
                                                                            dmc.NumberInput(
                                                                                id="filter-pctdeout-input",
                                                                                step=1,
                                                                                value=None,
                                                                                placeholder="bar",
                                                                                min=pctde_min,
                                                                                max=pctde_max,
                                                                                styles={"input": {"height": 28, "width": 68}},
                                                                            ),
                                                                            dmc.Slider(
                                                                                id="filter-pctdeout",
                                                                                min=pctde_min,
                                                                                max=pctde_max,
                                                                                step=1,
                                                                                value=None,
                                                                                marks=[],
                                                                                label=None,
                                                                                style={"width": 120, "marginLeft": 4, "marginRight": 4},
                                                                            ),
                                                                        ],
                                                                        gap="xs",
                                                                    ),
                                                                ],
                                                                gap="xs",
                                                            ),
                                                            dmc.Button(
                                                                "Apply",
                                                                id="apply-ts-filters",
                                                                variant="filled",
                                                                color="blue",
                                                                style={"marginLeft": 4},
                                                            ),
                                                            dmc.Button(
                                                                "Reset",
                                                                id="reset-ts-filters",
                                                                variant="outline",
                                                                color="gray",
                                                                disabled=True,
                                                                style={"marginLeft": 4},
                                                            ),
                                                            info_tooltip,  # This is your info button
                                                        ],
                                                        align="center",
                                                        gap="xs",
                                                        style={"marginBottom": 16, "flexWrap": "wrap"},
                                                    ),
                                            # Graphs below
                                            dmc.Stack(
                                                [
                                                    dcc.Graph(
                                                        id="voltage",
                                                        figure=make_ts_fig(
                                                            df_ts_default,
                                                            "uCell",
                                                            "Cell Voltage vs Runtime (uCell)",
                                                            "Cell voltage [V]",
                                                            None,
                                                            None,
                                                            False,
                                                            None,
                                                            False,
                                                        ),
                                                        style={"height": "450px"},

                                                    ),
                                                    dcc.Graph(
                                                        id="o2h2",
                                                        figure=make_ts_fig(
                                                            df_ts_default,
                                                            "concO2H2",
                                                            "O₂ in H₂ vs Runtime",
                                                            "O₂ concentration in H₂ [%]",
                                                            None,
                                                            None,
                                                            False,
                                                            None,
                                                            False,
                                                        ),
                                                        style={"height": "450px"},
                                                    ),
                                                    dcc.Graph(
                                                        id="h2o2",
                                                        figure=make_ts_fig(
                                                            df_ts_default,
                                                            "concH2O2",
                                                            "H₂ in O₂ vs Runtime",
                                                            "H₂ concentration in O₂ [%]",
                                                            None,
                                                            None,
                                                            False,
                                                            None,
                                                            False,
                                                        ),
                                                        style={"height": "450px"},
                                                    ),
                                                ],
                                                gap="md",
                                            ),
                                        ],
                                        withBorder=True,
                                        p="md",
                                        radius="md",
                                    ),
                                ],
                            ),
                        ],
                    ),

                    # Stores
                    dcc.Store(id="track-visible-samples", data=None),
                    dcc.Store(id="track-filters", data=None),
                    dcc.Store(id="filters-applied", data=False),
                ],
            ),
        ],
    )


# If your framework expects a callable layout, this is fine.
# If you need a component, use: layout = track_record_layout()
layout = track_record_layout

# =====================================================
# CALLBACK: TOGGLE HELP INFO
# =====================================================
@callback(
    Output("trackrecord-usage-open", "data"),
    Input("trackrecord-usage-toggle", "n_clicks"),
    State("trackrecord-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage_blockquote(n_clicks, is_open):
    if n_clicks is None:
        return no_update
    return not bool(is_open)


@callback(
    Output("trackrecord-usage-collapse", "opened"),
    Input("trackrecord-usage-open", "data"),
)
def sync_usage_blockquote(is_open):
    return bool(is_open)


# =====================================================
# Collapsible toggle for the performance of the tope 5 stacks
# =====================================================
@callback(
    Output("perf-collapse", "opened"),
    Output("perf-chevron-icon", "icon"),
    Input("perf-collapse-toggle", "n_clicks"),
    State("perf-collapse", "opened"),
    prevent_initial_call=True,
)
def toggle_perf_section(n, opened):
    if not n:
        return opened, "bi:chevron-down"
    new_state = not opened
    icon = "bi:chevron-up" if new_state else "bi:chevron-down"
    return new_state, icon

# =========================================================
# LEGEND SYNC STORE
# =========================================================

@callback(
    Output("track-visible-samples", "data"),
    Input("voltage", "restyleData"),
    Input("o2h2", "restyleData"),
    Input("h2o2", "restyleData"),
    State("track-visible-samples", "data"),
    prevent_initial_call=True,
)
def sync_legends(r1, r2, r3, visible):

    if not ctx.triggered:
        return visible

    restyle = ctx.triggered[0]["value"]
    if not restyle or "visible" not in restyle[0]:
        return visible

    # Plotly's restyleData can contain multiple indices and visibility
    # values (e.g. when double-clicking to isolate one trace). 

    indices = restyle[1]
    visibles = restyle[0]["visible"]

    # Normalise to lists
    if not isinstance(indices, list):
        indices = [indices]

    if not isinstance(visibles, list):
        visibles = [visibles] * len(indices)
    elif len(visibles) == 1 and len(indices) > 1:
        # Plotly sometimes sends a single visibility value for many indices
        visibles = visibles * len(indices)

    hidden = set(visible["hidden"]) if visible else set()

    for idx, vis in zip(indices, visibles):
        if vis == "legendonly":
            hidden.add(idx)
        elif vis is True:
            hidden.discard(idx)

    return {"hidden": sorted(hidden)}


# =========================================================
# APPLY TIMESERIES FILTERS
# =========================================================

@callback(
    Output("track-filters", "data"),
    Output("filters-applied", "data"),
    Output("reset-ts-filters", "disabled"),
    Output("reset-ts-filters", "color"),
    Input("apply-ts-filters", "n_clicks"),
    Input("reset-ts-filters", "n_clicks"),
    State("filter-jstck", "value"),
    State("filter-tandeout", "value"),
    State("filter-pctdeout", "value"),
    prevent_initial_call=True,
)
def apply_ts_filters(apply_clicks, reset_clicks, jstck, tandeout, pctdeout):

    trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

    # Reset button clicked
    if trigger == "reset-ts-filters":
        return None, False, True, "secondary"

    # Apply button clicked
    if trigger == "apply-ts-filters":
        # Check if any filter has a value
        has_filters = any(v is not None for v in [jstck, tandeout, pctdeout])
        
        if not has_filters:
            # No filters selected, return None and keep reset disabled
            return None, False, True, "secondary"
        
        # Filters selected, enable reset button and make it blue
        return {
            "jStck": jstck,
            "tAndeOut": tandeout,
            "pCtdeOut": pctdeout,
        }, True, False, "primary"

    return no_update, no_update, no_update, no_update


# =========================================================
# SYNC SLIDER + INPUT VALUES
# =========================================================

@callback(
    Output("filter-jstck", "value"),
    Output("filter-jstck-input", "value"),
    Output("filter-jstck-input", "className"),
    Input("filter-jstck", "value"),
    Input("filter-jstck-input", "value"),
    Input("reset-ts-filters", "n_clicks"),
)
def sync_jstck_value(slider_value, input_value, reset_clicks):

    if not ctx.triggered:
        return slider_value, input_value, ""

    trigger = ctx.triggered[0]["prop_id"].split(".")[0]

    # Reset button clicked
    if trigger == "reset-ts-filters":
        return None, None, ""

    if trigger == "filter-jstck":
        if slider_value is None:
            return None, None, ""
        value = _clamp(slider_value, JSTCK_MIN, JSTCK_MAX)
        return value, round(value, 2), ""

    if input_value is None:
        return None, None, ""

    value = _clamp(input_value, JSTCK_MIN, JSTCK_MAX)
    is_error = input_value < JSTCK_MIN or input_value > JSTCK_MAX
    return value, round(value, 2), "input-error" if is_error else ""


@callback(
    Output("filter-tandeout", "value"),
    Output("filter-tandeout-input", "value"),
    Output("filter-tandeout-input", "className"),
    Input("filter-tandeout", "value"),
    Input("filter-tandeout-input", "value"),
    Input("reset-ts-filters", "n_clicks"),
)
def sync_tandeout_value(slider_value, input_value, reset_clicks):

    if not ctx.triggered:
        return slider_value, input_value, ""

    trigger = ctx.triggered[0]["prop_id"].split(".")[0]

    # Reset button clicked
    if trigger == "reset-ts-filters":
        return None, None, ""

    if trigger == "filter-tandeout":
        if slider_value is None:
            return None, None, ""
        value = _clamp(slider_value, tande_min, tande_max)
        return value, round(value, 2), ""

    if input_value is None:
        return None, None, ""

    value = _clamp(input_value, tande_min, tande_max)
    is_error = input_value < tande_min or input_value > tande_max
    return value, round(value, 2), "input-error" if is_error else ""


@callback(
    Output("filter-pctdeout", "value"),
    Output("filter-pctdeout-input", "value"),
    Output("filter-pctdeout-input", "className"),
    Input("filter-pctdeout", "value"),
    Input("filter-pctdeout-input", "value"),
    Input("reset-ts-filters", "n_clicks"),
)
def sync_pctdeout_value(slider_value, input_value, reset_clicks):

    if not ctx.triggered:
        return slider_value, input_value, ""

    trigger = ctx.triggered[0]["prop_id"].split(".")[0]

    # Reset button clicked
    if trigger == "reset-ts-filters":
        return None, None, ""

    if trigger == "filter-pctdeout":
        if slider_value is None:
            return None, None, ""
        value = _clamp(slider_value, pctde_min, pctde_max)
        return value, round(value, 2), ""

    if input_value is None:
        return None, None, ""

    value = _clamp(input_value, pctde_min, pctde_max)
    is_error = input_value < pctde_min or input_value > pctde_max
    return value, round(value, 2), "input-error" if is_error else ""

# =========================================================
# TIMESERIES UPDATE (ZOOM + LEGEND + THEME)
# =========================================================

def apply_theme(fig, theme):
    template = "plotly_dark" if theme == "dark" else "plotly"
    fig.update_layout(template=template)
    return fig


@callback(
    Output("runtime-kpi", "figure"),
    Output("runtime-bar", "figure"),
    Output("voltage", "figure"),
    Output("o2h2", "figure"),
    Output("h2o2", "figure"),
    Input("voltage", "relayoutData"),
    Input("o2h2", "relayoutData"),
    Input("h2o2", "relayoutData"),
    Input("track-visible-samples", "data"),
    Input("track-filters", "data"),
    Input("theme-store", "data"),
    Input("reset-ts-filters", "n_clicks"),
    prevent_initial_call=True,
)
def update_timeseries(r_v, r_o2, r_h2, visible, filters, theme, reset_clicks):

    trigger = ctx.triggered[0]["prop_id"]
    valid_charts = {"voltage", "o2h2", "h2o2"}
    trigger_chart = trigger.split(".")[0] if trigger and trigger.split(".")[0] in valid_charts else None


    # -------------------------------------------------
    # Detect zoom range
    # -------------------------------------------------
    relayout_map = {
        "voltage.relayoutData": r_v,
        "o2h2.relayoutData": r_o2,
        "h2o2.relayoutData": r_h2,
    }

    relayout = relayout_map.get(trigger)

    x_range = None
    reset = False
    y_ranges: Dict[str, Optional[List[float]]] = {"voltage": None, "o2h2": None, "h2o2": None}
    y_resets = {"voltage": False, "o2h2": False, "h2o2": False}

    # Reset button clicked - reset all zoom
    if trigger == "reset-ts-filters.n_clicks":
        reset = True
        y_resets = {"voltage": True, "o2h2": True, "h2o2": True}
    elif relayout:
        if "xaxis.range[0]" in relayout:
            x_range = [
                relayout["xaxis.range[0]"],
                relayout["xaxis.range[1]"],
            ]
        elif relayout.get("xaxis.autorange"):
            reset = True

        if relayout and trigger_chart:
            if "yaxis.range[0]" in relayout and "yaxis.range[1]" in relayout:
                y_ranges[trigger_chart] = [
                    relayout["yaxis.range[0]"],
                    relayout["yaxis.range[1]"],
                ]
            elif relayout.get("yaxis.autorange"):
                y_resets[trigger_chart] = True

    # -------------------------------------------------
    # Build all timeseries figures
    # -------------------------------------------------
    # If no filters are applied, show all data
    if filters is None:
        df_filtered = df_ts.copy()
    else:
        df_filtered = filter_timeseries(df_ts, filters)

    voltage_fig = make_ts_fig(
        df_filtered,
        "uCell",
        "Cell Voltage vs Runtime (uCell)",
        "Cell voltage [V]",
        visible,
        x_range,
        reset,
        y_ranges["voltage"],
        y_resets["voltage"],
    )

    o2_fig = make_ts_fig(
        df_filtered,
        "concO2H2",
        "O₂ in H₂ vs Runtime",
        "O₂ concentration in H₂ [%]",
        visible,
        x_range,
        reset,
        y_ranges["o2h2"],
        y_resets["o2h2"],
    )

    h2_fig = make_ts_fig(
        df_filtered,
        "concH2O2",
        "H₂ in O₂ vs Runtime",
        "H₂ concentration in O₂ [%]",
        visible,
        x_range,
        reset,
        y_ranges["h2o2"],
        y_resets["h2o2"],
    )

    # -------------------------------------------------
    # Apply theme to ALL figures
    # -------------------------------------------------
    kpi_fig = copy.deepcopy(fig_kpi)
    runtime_fig = copy.deepcopy(fig_runtime)

    kpi_fig = apply_theme(kpi_fig, theme)
    runtime_fig = apply_theme(runtime_fig, theme)

    voltage_fig = apply_theme(voltage_fig, theme)
    o2_fig = apply_theme(o2_fig, theme)
    h2_fig = apply_theme(h2_fig, theme)

    return kpi_fig, runtime_fig, voltage_fig, o2_fig, h2_fig