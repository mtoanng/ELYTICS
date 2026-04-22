from dash import (
    html,
    dcc,
    callback,
    Output,
    Input,
    State,
    register_page,
    no_update,
    callback_context,
)
import dash_mantine_components as dmc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta, timezone
from dash_iconify import DashIconify

from services.backend_service import get_metadata, get_tabular

register_page(
    __name__,
    path="/sherlock/management/test-rig-activity",
    title="HOLMES - Sherlock - Test Rig Activity",
    name="HOLMES - Sherlock - Test Rig Activity",
)

# -------------------------------------------------
# CONSTANTS
# -------------------------------------------------

SENSORS = {
    "pAndeIn": {"title": "Pressure Anode Inlet (pAndeIn)", "unit": "bar"},
    "pCtdeOut": {"title": "Pressure Cathode Outlet (pCtdeOut)", "unit": "bar"},
    "uCell": {"title": "Cell Voltage (uCell)", "unit": "V"},
    "jStck": {"title": "Current Density (jStck)", "unit": "A/cm²"},
    "tAndeIn": {"title": "Temperature Anode Inlet (tAndeIn)", "unit": "°C"},
    "vfAndeIn": {"title": "Volume Flow Anode Inlet (vfAndeIn)", "unit": "L/min"},
}

SENSOR_KEYS = ["uCell", "jStck", "pAndeIn", "pCtdeOut", "tAndeIn", "vfAndeIn"]
PLOT_IDS = [
    "plot-uCell",
    "plot-jStck",
    "plot-pAndeIn",
    "plot-pCtdeOut",
    "plot-tAndeIn",
    "plot-vfAndeIn",
]
PLOT_HEIGHT_PX = 360

USAGE_BLOCKQUOTE_TEXT = [
    "Select a test rig from the dropdown to load its sensor data.",
    "Use the location filter to narrow down which test rigs are available.",
    "Use the time range to restrict the visible window of data.",
    "Zoom on any chart to synchronise the x-axis across all sensor plots.",
    "Data is 1-hour aggregated sensor readings per test rig.",
]

# -------------------------------------------------
# LAYOUT
# -------------------------------------------------

layout = dmc.Container(
    size="xl",
    py="md",
    children=[
        dmc.Stack(
            gap="md",
            children=[
                # ── Header ──────────────────────────────────────────
                dmc.Stack(
                    gap=2,
                    children=[
                        dmc.Group(
                            gap="xs",
                            align="center",
                            children=[
                                dmc.Title("Test Rig Activity", order=2),
                                dmc.ActionIcon(
                                    DashIconify(
                                        icon="material-symbols:info-outline", width=20
                                    ),
                                    id="activity-usage-toggle",
                                    variant="subtle",
                                    color="blue",
                                    size="md",
                                    radius="xl",
                                ),
                            ],
                        ),
                        dmc.Text(
                            "Timeseries sensor data per test rig (1-hour aggregated).",
                            c="dimmed",
                        ),
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
                            opened=False,
                            id="activity-usage-collapse",
                        ),
                    ],
                ),
                # ── Filters ─────────────────────────────────────────
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
                                        id="activity-location-filter",
                                        options=[],
                                        value=[],
                                        multi=True,
                                        searchable=True,
                                        clearable=True,
                                        placeholder="All locations",
                                        style={"width": "100%"},
                                    ),
                                    label="Location",
                                    htmlFor="activity-location-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "180px"},
                                ),
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="activity-testrig-filter",
                                        options=[],
                                        value=[],
                                        multi=True,
                                        searchable=True,
                                        clearable=True,
                                        placeholder="Loading test rigs...",
                                        style={"width": "100%"},
                                    ),
                                    label="Test Rig",
                                    htmlFor="activity-testrig-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "200px"},
                                ),
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="activity-date-range",
                                        options=[
                                            {"label": "Last 7 days", "value": 7},
                                            {"label": "Last 14 days", "value": 14},
                                            {"label": "Last 30 days", "value": 30},
                                        ],
                                        value=7,
                                        clearable=False,
                                        style={"width": "100%"},
                                    ),
                                    label="Time Range",
                                    htmlFor="activity-date-range",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": "0 0 180px"},
                                ),
                                dmc.Button(
                                    "Reset",
                                    id="activity-reset-btn",
                                    n_clicks=0,
                                    variant="light",
                                    radius="md",
                                    style={"flex": "0 0 auto", "alignSelf": "flex-end"},
                                ),
                            ],
                        ),
                    ],
                ),
                # ── Sensor plots ─────────────────────────────────────
                dmc.Paper(
                    withBorder=True,
                    p="md",
                    radius="md",
                    children=dmc.SimpleGrid(
                        cols=2,
                        spacing="md",
                        verticalSpacing="md",
                        children=[
                            dmc.Box(
                                pos="relative",
                                children=[
                                    dmc.LoadingOverlay(
                                        id=f"{plot_id}-loading-overlay",
                                        visible=True,
                                        zIndex=10,
                                        loaderProps={"color": "blue", "size": "lg", "variant": "dots"},
                                        overlayProps={"radius": "sm", "blur": 1},
                                    ),
                                    dmc.Box(
                                        id=f"{plot_id}-wrapper",
                                        style={"opacity": 0},
                                        children=dcc.Graph(
                                            id=plot_id,
                                            config={"responsive": True},
                                            style={"height": f"{PLOT_HEIGHT_PX}px"},
                                        ),
                                    ),
                                ],
                            )
                            for plot_id in PLOT_IDS
                        ],
                    ),
                ),
                # ── Stores ────────────────────────────────────────────
                dcc.Store(id="activity-metadata-store"),
                dcc.Store(id="activity-raw-store", data=None),
                dcc.Store(id="activity-usage-open", data=False),
            ],
        )
    ],
)

# =========================================================
# INFO PANEL COLLAPSE
# =========================================================


@callback(
    Output("activity-usage-open", "data"),
    Input("activity-usage-toggle", "n_clicks"),
    State("activity-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage(_, is_open):
    return not bool(is_open)


@callback(
    Output("activity-usage-collapse", "opened"),
    Input("activity-usage-open", "data"),
)
def sync_usage_collapse(is_open):
    return bool(is_open)


# =========================================================
# STEP 1 — load metadata on page render
# =========================================================


@callback(
    Output("activity-metadata-store", "data"),
    Input("activity-testrig-filter", "id"),  # fires once on mount
)
def init_metadata(_):
    return get_metadata("sherlock", "testrig_activity")


# =========================================================
# STEP 2 — populate filter dropdowns from metadata
# =========================================================


@callback(
    Output("activity-testrig-filter", "options"),
    Output("activity-testrig-filter", "value"),
    Output("activity-location-filter", "options"),
    Output("activity-location-filter", "value"),
    Input("activity-metadata-store", "data"),
    Input("activity-location-filter", "value"),
    State("activity-testrig-filter", "value"),
)
def populate_filters(meta, selected_locations, current_testrigs):
    if not meta:
        return [], [], [], []

    df = pd.DataFrame(meta)

    # Build location options from full metadata
    location_options = []
    normalized_locations = []
    if "location" in df.columns:
        locations = sorted(df["location"].dropna().unique().tolist())
        location_options = [{"label": l, "value": l} for l in locations]
        tbp_locations = [
            loc for loc in locations if "tbp" in str(loc).strip().lower()
        ]
        default_locations = tbp_locations or locations
        normalized_locations = selected_locations or default_locations
        if normalized_locations:
            df = df[df["location"].isin(normalized_locations)]

    ids = sorted(df["testrig_id"].dropna().unique().tolist(), key=str)
    testrig_options = [{"label": str(i), "value": str(i)} for i in ids]
    available_ids = {str(i) for i in ids}

    if current_testrigs:
        selected_testrigs = [
            str(i) for i in current_testrigs if str(i) in available_ids
        ]
    else:
        selected_testrigs = [str(i) for i in ids]

    return testrig_options, selected_testrigs, location_options, normalized_locations


# =========================================================
# STEP 3 — fetch tabular data when test rig selection changes
# =========================================================


@callback(
    Output("activity-raw-store", "data"),
    Input("activity-testrig-filter", "value"),
    prevent_initial_call=True,
)
def load_testrig_data(testrig_ids):
    if not testrig_ids:
        return []

    frames = []
    for testrig_id in testrig_ids:
        df = get_tabular(
            "sherlock",
            "testrig_activity",
            filters={"testrig_id": str(testrig_id)},
        )
        if not df.empty:
            frames.append(df)

    if not frames:
        return []

    merged_df = pd.concat(frames, ignore_index=True)
    return merged_df.drop_duplicates().to_dict("records")


@callback(
    Output("plot-uCell-loading-overlay", "visible"),
    Output("plot-jStck-loading-overlay", "visible"),
    Output("plot-pAndeIn-loading-overlay", "visible"),
    Output("plot-pCtdeOut-loading-overlay", "visible"),
    Output("plot-tAndeIn-loading-overlay", "visible"),
    Output("plot-vfAndeIn-loading-overlay", "visible"),
    Output("plot-uCell-wrapper", "style"),
    Output("plot-jStck-wrapper", "style"),
    Output("plot-pAndeIn-wrapper", "style"),
    Output("plot-pCtdeOut-wrapper", "style"),
    Output("plot-tAndeIn-wrapper", "style"),
    Output("plot-vfAndeIn-wrapper", "style"),
    Input("activity-testrig-filter", "value"),
    Input("activity-raw-store", "data"),
    Input("plot-uCell", "figure"),
    Input("plot-jStck", "figure"),
    Input("plot-pAndeIn", "figure"),
    Input("plot-pCtdeOut", "figure"),
    Input("plot-tAndeIn", "figure"),
    Input("plot-vfAndeIn", "figure"),
    Input("plot-uCell", "loading_state"),
    Input("plot-jStck", "loading_state"),
    Input("plot-pAndeIn", "loading_state"),
    Input("plot-pCtdeOut", "loading_state"),
    Input("plot-tAndeIn", "loading_state"),
    Input("plot-vfAndeIn", "loading_state"),
)
def sync_plots_loading_state(
    _,
    data,
    ucell_fig,
    jstck_fig,
    pandein_fig,
    pctdeout_fig,
    tandein_fig,
    vfandein_fig,
    ucell_loading,
    jstck_loading,
    pandein_loading,
    pctdeout_loading,
    tandein_loading,
    vfandein_loading,
):
    ctx = callback_context
    triggered_prop = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    # Show loader immediately when filter selection changes.
    if triggered_prop == "activity-testrig-filter.value":
        return (
            True, True, True, True, True, True,
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
        )

    if data is None:
        return (
            True, True, True, True, True, True,
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
        )

    figure_states = [
        ucell_fig,
        jstck_fig,
        pandein_fig,
        pctdeout_fig,
        tandein_fig,
        vfandein_fig,
    ]
    if any(fig is None for fig in figure_states):
        return (
            True, True, True, True, True, True,
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
        )

    plot_loading_states = [
        ucell_loading,
        jstck_loading,
        pandein_loading,
        pctdeout_loading,
        tandein_loading,
        vfandein_loading,
    ]
    if any((state or {}).get("is_loading", False) for state in plot_loading_states):
        return (
            True, True, True, True, True, True,
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
            {"opacity": 0},
        )

    return (
        False, False, False, False, False, False,
        {"opacity": 1, "transition": "opacity 120ms ease"},
        {"opacity": 1, "transition": "opacity 120ms ease"},
        {"opacity": 1, "transition": "opacity 120ms ease"},
        {"opacity": 1, "transition": "opacity 120ms ease"},
        {"opacity": 1, "transition": "opacity 120ms ease"},
        {"opacity": 1, "transition": "opacity 120ms ease"},
    )


# =========================================================
# RESET FILTERS
# =========================================================


@callback(
    Output("activity-location-filter", "value", allow_duplicate=True),
    Output("activity-date-range", "value"),
    Input("activity-reset-btn", "n_clicks"),
    State("activity-location-filter", "options"),
    prevent_initial_call=True,
)
def reset_filters_to_default(_, location_options):
    options = location_options or []
    option_values = [opt.get("value") for opt in options if opt.get("value") is not None]
    tbp_values = [
        val for val in option_values if "tbp" in str(val).strip().lower()
    ]
    return (tbp_values or option_values), 7


# =========================================================
# BUILD CHARTS
# =========================================================


@callback(
    Output("plot-uCell", "figure"),
    Output("plot-jStck", "figure"),
    Output("plot-pAndeIn", "figure"),
    Output("plot-pCtdeOut", "figure"),
    Output("plot-tAndeIn", "figure"),
    Output("plot-vfAndeIn", "figure"),
    Input("activity-raw-store", "data"),
    Input("activity-date-range", "value"),
    Input("theme-store", "data"),
    Input("plot-uCell", "relayoutData"),
    Input("plot-jStck", "relayoutData"),
    Input("plot-pAndeIn", "relayoutData"),
    Input("plot-pCtdeOut", "relayoutData"),
    Input("plot-tAndeIn", "relayoutData"),
    Input("plot-vfAndeIn", "relayoutData"),
    State("activity-testrig-filter", "value"),
)
def update_plots(data, last_n_days, theme, r1, r2, r3, r4, r5, r6, testrig_ids):
    FIG_HEIGHT = PLOT_HEIGHT_PX
    template = "plotly_dark" if theme == "dark" else "plotly"

    def empty_fig(title="No data"):
        fig = go.Figure()
        fig.update_layout(
            height=FIG_HEIGHT,
            template=template,
            title=dict(text=title, y=0.96, yanchor="top"),
            margin=dict(l=48, r=20, t=48, b=40),
        )
        return fig

    if data is None:
        return tuple(no_update for _ in SENSOR_KEYS)

    if not data:
        return tuple(empty_fig() for _ in SENSOR_KEYS)

    df = pd.DataFrame(data)

    # Locate time column
    time_col = next(
        (c for c in ("time_ts", "time", "timestamp") if c in df.columns), None
    )
    if time_col is None:
        return tuple(empty_fig("No time column found") for _ in SENSOR_KEYS)

    df[time_col] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
    df = df.dropna(subset=[time_col]).sort_values(time_col)

    if last_n_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=last_n_days)
        df = df[df[time_col] >= cutoff]

    # ── Zoom sync ────────────────────────────────────────
    x_range = None
    reset_autorange = False
    ctx = callback_context
    if ctx.triggered and "relayoutData" in ctx.triggered[0]["prop_id"]:
        relayout = ctx.triggered[0]["value"] or {}
        if "xaxis.range[0]" in relayout:
            x_range = [relayout["xaxis.range[0]"], relayout["xaxis.range[1]"]]
        elif relayout.get("xaxis.autorange") is True:
            reset_autorange = True

    # uirevision key: changes when testrig changes or when an explicit zoom is applied
    selected_testrigs = [str(tid) for tid in (testrig_ids or [])]
    selected_key = ",".join(sorted(selected_testrigs)) if selected_testrigs else "none"
    base_rev = f"activity-{selected_key}"
    uirev_key = f"zoom-{x_range}-{selected_key}" if x_range else base_rev

    def make_fig(col):
        if col not in df.columns:
            return empty_fig(f"{SENSORS[col]['title']} — column not available")

        trace_col = next(
            (c for c in ("testrig_id", "testrig_label", "testrig_name") if c in df.columns),
            None,
        )

        fig = go.Figure()
        if trace_col is None:
            fig.add_trace(
                go.Scatter(
                    x=df[time_col],
                    y=df[col],
                    mode="lines",
                    name="Testrig",
                    line=dict(width=1.5),
                    hovertemplate=(
                        f"<b>{col}</b>: %{{y:.3f}} {SENSORS[col]['unit']}<br>"
                        "Time: %{x}<extra></extra>"
                    ),
                )
            )
        else:
            for trace_name, group_df in df.groupby(trace_col):
                fig.add_trace(
                    go.Scatter(
                        x=group_df[time_col],
                        y=group_df[col],
                        mode="lines",
                        name=str(trace_name),
                        line=dict(width=1.5),
                        hovertemplate=(
                            f"<b>{col}</b>: %{{y:.3f}} {SENSORS[col]['unit']}<br>"
                            "Time: %{x}<extra></extra>"
                        ),
                    )
                )
        fig.update_layout(
            title=dict(
                text=f"{SENSORS[col]['title']}",
                y=0.96,
                yanchor="top",
                pad=dict(t=0),
            ),
            xaxis_title="Time",
            yaxis_title=f"{col} [{SENSORS[col]['unit']}]",
            hovermode="x unified",
            template=template,
            height=FIG_HEIGHT,
            margin=dict(l=48, r=20, t=48, b=40),
            uirevision=uirev_key,
        )
        if x_range:
            fig.update_xaxes(range=x_range)
        elif reset_autorange:
            fig.update_xaxes(autorange=True)
        return fig

    return tuple(make_fig(col) for col in SENSOR_KEYS)


#             html.Hr(style={"margin": "12px 0"}),

#             html.Label("Location:", style={"fontWeight": "600", "marginBottom": "6px"}),
#             dcc.Dropdown(
#                 id="activity-location-filter",
#                 options=[],
#                 value=[],
#                 multi=True,
#                 placeholder="Select location(s)"
#             ),

#             html.Label("Test Rig:", style={"fontWeight": "600", "marginBottom": "6px", "marginTop": "8px"}),
#             dcc.Dropdown(
#                 id="activity-testrig-filter",
#                 options=[],
#                 value=[],
#                 multi=True,
#                 placeholder="Select test rig(s)"
#             ),

#             html.Hr(style={"margin": "12px 0"}),

#             # ---- Reset Button ----
#             html.Button(
#                 "Reset selection",
#                 id="activity-reset-selection-btn",
#                 n_clicks=0,
#                 style={
#                     "width": "100%",
#                     "borderRadius": "6px",
#                     "padding": "6px 12px",
#                     "fontWeight": "600",
#                     "fontSize": "14px",
#                     "backgroundColor": "#f1f6ff",   # very light blue
#                     "border": "1px solid #b6ccff",  # soft blue border
#                     "color": "black",             # black text

#                     "cursor": "pointer",
#                 },
#             ),

#             dcc.Store(id="activity-reset-counter", data=0),

#             # Legend Store
#             dcc.Store(
#                 id="activity-visible-testrigs",
#                 data=None  # None = default (all visible)
#             ),

#         ], style={
#             "width": "260px",
#             "minWidth": "260px",
#             "maxWidth": "260px",
#             "flexShrink": "0",
#             "padding": "12px"
#         }),

#         # =========================
#         # RIGHT PLOTS COLUMN
#         # =========================
#         html.Div([

#             html.Div([
#                 dcc.Graph(id="plot-uCell",    style={"width": "48%", "display": "inline-block"}),
#                 dcc.Graph(id="plot-jStck",    style={"width": "48%", "display": "inline-block", "float": "right"}),

#                 dcc.Graph(id="plot-pAndeIn",  style={"width": "48%", "display": "inline-block"}),
#                 dcc.Graph(id="plot-pCtdeOut", style={"width": "48%", "display": "inline-block", "float": "right"}),

#                 dcc.Graph(id="plot-tAndeIn",  style={"width": "48%", "display": "inline-block"}),
#                 dcc.Graph(id="plot-vfAndeIn", style={"width": "48%", "display": "inline-block", "float": "right"}),
#             ])

#         ], style={
#             "flexGrow": "1",
#             "minWidth": "0",
#             "paddingRight": "5px",
#         })

#     ], style={
#         "display": "flex",
#         "alignItems": "flex-start",
#         "width": "100%"
#     })
# ])


# # -------------------------------------------------
# # Reset Filters
# # -------------------------------------------------
# from dash import no_update

# @callback(
#     Output("activity-location-filter", "value"),
#     Output("activity-testrig-filter", "value"),
#     Output("date-range", "value"),
#     Output("activity-reset-counter", "data"),
#     Output("activity-visible-testrigs", "data", allow_duplicate=True),
#     Input("activity-reset-selection-btn", "n_clicks"),
#     State("activity-reset-counter", "data"),
#     prevent_initial_call=True
# )
# def reset_filters(n_clicks, counter):
#     return [], [], 7, counter + 1, None


# # -------------------------------------------------
# # Legends Store Sync
# # -------------------------------------------------
# @callback(
#     Output("activity-visible-testrigs", "data"),
#     Input("plot-uCell", "restyleData"),
#     Input("plot-jStck", "restyleData"),
#     Input("plot-pAndeIn", "restyleData"),
#     Input("plot-pCtdeOut", "restyleData"),
#     Input("plot-tAndeIn", "restyleData"),
#     Input("plot-vfAndeIn", "restyleData"),
#     State("activity-visible-testrigs", "data"),
#     prevent_initial_call=True,
# )
# def sync_legends(r1, r2, r3, r4, r5, r6, visible):

#     ctx = dash.callback_context
#     if not ctx.triggered:
#         return visible

#     restyle = ctx.triggered[0]["value"]

#     # Only care about visibility toggles
#     if not restyle or "visible" not in restyle[0]:
#         return visible

#     indices = restyle[1]
#     new_visibility = restyle[0]["visible"][0]

#     # Initialize if first interaction
#     if visible is None:
#         return {
#             "mode": "explicit",
#             "hidden": indices if new_visibility == "legendonly" else []
#         }

#     hidden = set(visible.get("hidden", []))

#     for idx in indices:
#         if new_visibility == "legendonly":
#             hidden.add(idx)
#         else:
#             hidden.discard(idx)

#     return {
#         "mode": "explicit",
#         "hidden": list(hidden)
#     }


# # -------------------------------------------------
# # CALLBACK
# # -------------------------------------------------

# @callback(
#     Output("plot-uCell", "figure"),
#     Output("plot-jStck", "figure"),
#     Output("plot-pAndeIn", "figure"),
#     Output("plot-pCtdeOut", "figure"),
#     Output("plot-tAndeIn", "figure"),
#     Output("plot-vfAndeIn", "figure"),

#     Output("activity-location-filter", "options"),
#     Output("activity-testrig-filter", "options"),

#     Input("activity-location-filter", "value"),
#     Input("activity-testrig-filter", "value"),

#     Input("date-range", "value"),

#     Input("plot-uCell", "relayoutData"),
#     Input("plot-jStck", "relayoutData"),
#     Input("plot-pAndeIn", "relayoutData"),
#     Input("plot-pCtdeOut", "relayoutData"),
#     Input("plot-tAndeIn", "relayoutData"),
#     Input("plot-vfAndeIn", "relayoutData"),

#     Input("theme-store", "data"),
#     Input("activity-reset-counter", "data"),

#     Input("activity-visible-testrigs", "data"),

# )
# def update_plots(
#     selected_locations,
#     selected_testrigs,
#     last_n_days,
#     r1, r2, r3, r4, r5, r6,
#     theme_store,
#     reset_counter,
#     visible_testrigs,
# ):

#     # ----------------------------
#     # LOAD DATA
#     # ----------------------------

#     sql = service.load_query("queries/testrig_activity_overview.sql")
#     sql = sql.replace("__LAST_N_DAYS__", str(last_n_days))

#     df = service.execute_query(sql)
#     df["time_ts"] = pd.to_datetime(df["time_ts"], utc=True)
#     df = df.sort_values("time_ts")

#     # ----------------------------
#     # LOCATION OPTIONS
#     # ----------------------------

#     locations = sorted(df["testrig_location"].dropna().unique())
#     location_options = [{"label": l, "value": l} for l in locations]

#     if selected_locations:
#         df = df[df["testrig_location"].isin(selected_locations)]

#     # ----------------------------
#     # TESTRIG OPTIONS (DEPENDENT)
#     # ----------------------------

#     testrigs = (
#         df[["testrig_label"]]
#         .dropna()
#         .drop_duplicates()
#         .sort_values("testrig_label")
#     )

#     testrig_options = [
#         {"label": t, "value": t}
#         for t in testrigs["testrig_label"]
#     ]

#     if selected_testrigs:
#         df = df[df["testrig_label"].isin(selected_testrigs)]

#     # ----------------------------
#     # ZOOM SYNC
#     # ----------------------------
#     x_range = None
#     reset_autorange = False

#     # Detect reset button trigger
#     force_reset = (
#         ctx.triggered
#         and ctx.triggered[0]["prop_id"] == "activity-reset-counter.data"
#     )

#     if force_reset:
#         # Treat reset button like a double-click reset
#         reset_autorange = True
#     else:
#         for relayout in (r1, r2, r3, r4, r5, r6):
#             if not relayout:
#                 continue

#             # Drag zoom
#             if "xaxis.range[0]" in relayout:
#                 x_range = [
#                     relayout["xaxis.range[0]"],
#                     relayout["xaxis.range[1]"],
#                 ]
#                 break

#             # Double-click reset
#             if relayout.get("xaxis.autorange") is True:
#                 reset_autorange = True
#                 break

#     template = "plotly_dark" if theme_store == "dark" else "plotly"


#     # ----------------------------
#     # FIGURE BUILDER
#     # ----------------------------

#     def make_fig(col):

#         fig = go.Figure()

#         hidden = set(visible_testrigs.get("hidden", [])) if visible_testrigs else set()

#         for i, (label, grp) in enumerate(df.groupby("testrig_label")):

#             if label not in TESTRIG_COLORS:
#                 TESTRIG_COLORS[label] = PALETTE[len(TESTRIG_COLORS) % len(PALETTE)]


#             visible = "legendonly" if i in hidden else True

#             fig.add_trace(
#                 go.Scatter(
#                     x=grp["time_ts"],
#                     y=grp[col],
#                     mode="lines",
#                     name=label,
#                     visible=visible,
#                     line=dict(width=1.5, color=TESTRIG_COLORS[label]),
#                     hovertemplate=(
#                         "Testrig: %{text}<br>"
#                         "Time: %{x}<br>"
#                         f"{col}: %{{y}}<extra></extra>"
#                     ),
#                     text=[label] * len(grp),
#                 )
#             )

#         fig.update_layout(
#             title=f"{SENSORS[col]['title']} - Last {last_n_days} Days",
#             xaxis_title="Time",
#             yaxis_title=f"{col} [{SENSORS[col]['unit']}]",
#             hovermode="x unified",
#             template=template,
#             uirevision=None if force_reset else f"timeseries-sync-{reset_counter}",
#             margin=dict(l=40, r=20, t=40, b=30),
#         )

#         if x_range:
#             fig.update_xaxes(range=x_range)
#         elif reset_autorange:
#             fig.update_xaxes(range=None, autorange=True)

#         return fig

#     return (
#         make_fig("uCell"),
#         make_fig("jStck"),
#         make_fig("pAndeIn"),
#         make_fig("pCtdeOut"),
#         make_fig("tAndeIn"),
#         make_fig("vfAndeIn"),
#         location_options,
#         testrig_options
#     )
