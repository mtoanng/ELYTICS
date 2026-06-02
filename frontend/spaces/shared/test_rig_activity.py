from dash import (
    register_page,
    callback,
    Output,
    Input,
    State,
    no_update,
    callback_context,
    dcc,
    html,
)
import dash_mantine_components as dmc
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta, timezone
from dash_iconify import DashIconify

from config.signals import get_signal_title, get_signal_unit
from services.backend_service import get_metadata, get_timeseries

# -------------------------------------------------
# CONSTANTS
# -------------------------------------------------

SENSORS = {
    "u_cell_avg": {"title": get_signal_title("u_cell_avg"), "unit": get_signal_unit("u_cell_avg")},
    "j": {"title": get_signal_title("j"), "unit": get_signal_unit("j")},
    "p_an_in": {"title": get_signal_title("p_an_in"), "unit": get_signal_unit("p_an_in")},
    "p_cat_out": {"title": get_signal_title("p_cat_out"), "unit": get_signal_unit("p_cat_out")},
    "t_an_in": {"title": get_signal_title("t_an_in"), "unit": get_signal_unit("t_an_in")},
    "vf_an_in": {"title": get_signal_title("vf_an_in"), "unit": get_signal_unit("vf_an_in")},
}

SENSOR_KEYS = list(SENSORS.keys())
PLOT_HEIGHT_PX = 360

USAGE_BLOCKQUOTE_TEXT = [
    "Select a test rig from the dropdown to load its sensor data.",
    "Use the location filter to narrow down which test rigs are available.",
    "Use the time range to restrict the visible window of data.",
    "Zoom on any chart to synchronise the x-axis across all sensor plots.",
    "Data is 1-hour aggregated sensor readings per test rig.",
]


def _resolve_location_column(df: pd.DataFrame) -> str | None:
    for column in ("testrig_location", "location", "raw_location"):
        if column in df.columns:
            return column
    return None


def _get_time_range_bounds(days: int | None) -> tuple[str, str]:
    range_days = days or 7
    now = datetime.now(timezone.utc)
    # Round end up to end-of-day and start down to start-of-day so that
    # requests within the same calendar day share the same cache key.
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    start_day = (now - timedelta(days=range_days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start_day.isoformat(), end.isoformat()


def _build_testrig_label_map(meta: list[dict] | None) -> dict[str, str]:
    if not meta:
        return {}

    df = pd.DataFrame(meta)
    if "testrig_id" not in df.columns:
        return {}

    location_col = _resolve_location_column(df)
    label_map: dict[str, str] = {}
    for _, row in df.dropna(subset=["testrig_id"]).iterrows():
        testrig_id = str(row["testrig_id"])
        location = row.get(location_col) if location_col else None
        if pd.notna(location) and str(location).strip():
            label_map[testrig_id] = f"{testrig_id} - {location}"
        else:
            label_map[testrig_id] = testrig_id
    return label_map


def create_test_rig_activity_page(ns: str):
    """Factory to create a test rig activity page with namespaced component IDs.

    Args:
        ns: Namespace prefix for component IDs (e.g., "sherlock", "enola")

    Returns:
        tuple: (layout, callbacks_dict) - layout component and dict of callback functions
    """

    # Build plot IDs with namespace
    PLOT_IDS = [f"{ns}-plot-{key}" for key in SENSOR_KEYS]

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
                                        id=f"{ns}-activity-usage-toggle",
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
                                id=f"{ns}-activity-usage-collapse",
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
                                            id=f"{ns}-activity-location-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            searchable=True,
                                            clearable=True,
                                            placeholder="All locations",
                                            style={"width": "100%"},
                                        ),
                                        label="Location",
                                        htmlFor=f"{ns}-activity-location-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": 1, "minWidth": "180px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id=f"{ns}-activity-testrig-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            searchable=True,
                                            clearable=True,
                                            placeholder="Loading test rigs...",
                                            style={"width": "100%"},
                                        ),
                                        label="Test Rig",
                                        htmlFor=f"{ns}-activity-testrig-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": 1, "minWidth": "200px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id=f"{ns}-activity-date-range",
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
                                        htmlFor=f"{ns}-activity-date-range",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "0 0 180px"},
                                    ),
                                    dmc.Button(
                                        "Reset",
                                        id=f"{ns}-activity-reset-btn",
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
                    dcc.Store(id=f"{ns}-activity-metadata-store"),
                    dcc.Store(id=f"{ns}-activity-raw-store", data=None),
                    dcc.Store(id=f"{ns}-activity-is-fetching", data=True),
                    dcc.Store(id=f"{ns}-activity-usage-open", data=False),
                ],
            )
        ],
    )

    # =========================================================
    # INFO PANEL COLLAPSE
    # =========================================================

    @callback(
        Output(f"{ns}-activity-usage-open", "data"),
        Input(f"{ns}-activity-usage-toggle", "n_clicks"),
        State(f"{ns}-activity-usage-open", "data"),
        prevent_initial_call=True,
    )
    def toggle_usage(_, is_open):
        return not bool(is_open)

    @callback(
        Output(f"{ns}-activity-usage-collapse", "opened"),
        Input(f"{ns}-activity-usage-open", "data"),
    )
    def sync_usage_collapse(is_open):
        return bool(is_open)

    # =========================================================
    # STEP 1 — load metadata on page render
    # =========================================================

    @callback(
        Output(f"{ns}-activity-metadata-store", "data"),
        Input(f"{ns}-activity-testrig-filter", "id"),  # fires once on mount
    )
    def init_metadata(_):
        return get_metadata("sherlock", "testrig_activity")

    # =========================================================
    # STEP 2 — populate filter dropdowns from metadata
    # =========================================================

    @callback(
        Output(f"{ns}-activity-testrig-filter", "options"),
        Output(f"{ns}-activity-testrig-filter", "value"),
        Output(f"{ns}-activity-location-filter", "options"),
        Output(f"{ns}-activity-location-filter", "value"),
        Input(f"{ns}-activity-metadata-store", "data"),
        Input(f"{ns}-activity-location-filter", "value"),
        State(f"{ns}-activity-testrig-filter", "value"),
    )
    def populate_filters(meta, selected_locations, current_testrigs):
        if not meta:
            return [], [], [], []

        df = pd.DataFrame(meta)

        # Build location options from full metadata
        location_options = []
        normalized_locations = []
        location_col = _resolve_location_column(df)
        if location_col:
            locations = sorted(df[location_col].dropna().unique().tolist())
            location_options = [{"label": l, "value": l} for l in locations]
            tbp_locations = [
                loc for loc in locations if "tbp" in str(loc).strip().lower()
            ]
            default_locations = tbp_locations or locations
            normalized_locations = selected_locations or default_locations
            if normalized_locations:
                df = df[df[location_col].isin(normalized_locations)]

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
    # STEP 3 — fetch timeseries data when filters change
    # =========================================================

    @callback(
        Output(f"{ns}-activity-is-fetching", "data", allow_duplicate=True),
        Input(f"{ns}-activity-testrig-filter", "value"),
        Input(f"{ns}-activity-date-range", "value"),
        prevent_initial_call=True,
    )
    def mark_fetching_start(_testrig_ids, _date_range):
        return True

    @callback(
        Output(f"{ns}-activity-raw-store", "data"),
        Output(f"{ns}-activity-is-fetching", "data"),
        Input(f"{ns}-activity-testrig-filter", "value"),
        Input(f"{ns}-activity-date-range", "value"),
        State(f"{ns}-activity-metadata-store", "data"),
        prevent_initial_call=True,
    )
    def load_testrig_data(testrig_ids, last_n_days, metadata_rows):
        if not testrig_ids:
            return []

        start, end = _get_time_range_bounds(last_n_days)
        testrig_labels = _build_testrig_label_map(metadata_rows)
        frames = []
        for testrig_id in testrig_ids:
            df = get_timeseries(
                "sherlock",
                "testrig_activity",
                start=start,
                end=end,
                columns=SENSOR_KEYS,
                time_column="time_ts",
                filters={"testrig_id": str(testrig_id)},
            )
            if not df.empty:
                df = df.copy()
                df["testrig_id"] = str(testrig_id)
                df["testrig_label"] = testrig_labels.get(str(testrig_id), str(testrig_id))
                frames.append(df)

        if not frames:
            return [], False

        merged_df = pd.concat(frames, ignore_index=True)
        return merged_df.drop_duplicates().to_dict("records"), False

    @callback(
        *[Output(f"{ns}-plot-{key}-loading-overlay", "visible") for key in SENSOR_KEYS],
        *[Output(f"{ns}-plot-{key}-wrapper", "style") for key in SENSOR_KEYS],
        Input(f"{ns}-activity-is-fetching", "data"),
    )
    def sync_plots_loading_state(is_fetching):
        if is_fetching:
            return (
                True, True, True, True, True, True,
                {"opacity": 0}, {"opacity": 0}, {"opacity": 0},
                {"opacity": 0}, {"opacity": 0}, {"opacity": 0},
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
        Output(f"{ns}-activity-location-filter", "value", allow_duplicate=True),
        Output(f"{ns}-activity-date-range", "value"),
        Input(f"{ns}-activity-reset-btn", "n_clicks"),
        State(f"{ns}-activity-location-filter", "options"),
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
        *[Output(f"{ns}-plot-{key}", "figure") for key in SENSOR_KEYS],
        Input(f"{ns}-activity-raw-store", "data"),
        Input("theme-store", "data"),
        *[Input(f"{ns}-plot-{key}", "relayoutData") for key in SENSOR_KEYS],
        State(f"{ns}-activity-testrig-filter", "value"),
    )
    def update_plots(data, theme, *relayout_and_testrig):
        relayout_data = relayout_and_testrig[:-1]
        testrig_ids = relayout_and_testrig[-1]
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
            (c for c in ("bucket_start", "time_ts", "time", "timestamp") if c in df.columns), None
        )
        if time_col is None:
            return tuple(empty_fig("No time column found") for _ in SENSOR_KEYS)

        df[time_col] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
        df = df.dropna(subset=[time_col]).sort_values(time_col)

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
            # backend auto aggregates for bucketing
            data_col = f"{col}_avg"
            if data_col not in df.columns:
                return empty_fig(f"{SENSORS[col]['title']} — column not available")

            trace_col = next(
                (c for c in ("testrig_label", "testrig_id", "testrig_name") if c in df.columns),
                None,
            )

            fig = go.Figure()
            if trace_col is None:
                fig.add_trace(
                    go.Scatter(
                        x=df[time_col],
                        y=df[data_col],
                        mode="lines",
                        name="Testrig",
                        line=dict(width=1.5),
                        hovertemplate=(
                            f"<b>{SENSORS[col]['title']}</b>: %{{y:.3f}} {SENSORS[col]['unit']}<br>"
                            "Time: %{x}<extra></extra>"
                        ),
                    )
                )
            else:
                for trace_name, group_df in df.groupby(trace_col):
                    fig.add_trace(
                        go.Scatter(
                            x=group_df[time_col],
                            y=group_df[data_col],
                            mode="lines",
                            name=str(trace_name),
                            line=dict(width=1.5),
                            hovertemplate=(
                                f"<b>{SENSORS[col]['title']}</b>: %{{y:.3f}} {SENSORS[col]['unit']}<br>"
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
                yaxis_title=f"{SENSORS[col]['title']} [{SENSORS[col]['unit']}]",
                hovermode="x unified",
                hoverlabel=dict(
                    bgcolor="#1a1b1e" if template == "plotly_dark" else "#ffffff",
                    font_color="#c1c2c5" if template == "plotly_dark" else "#000000",
                    bordercolor="#373a40" if template == "plotly_dark" else "#cccccc",
                ),
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

    return layout
