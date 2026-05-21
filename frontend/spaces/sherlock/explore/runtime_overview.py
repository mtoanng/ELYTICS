from dash import html, dcc, callback, Output, Input, State, register_page, no_update, clientside_callback
from dash.dcc.express import send_data_frame
import dash_mantine_components as dmc
from dash_iconify import DashIconify

import pandas as pd
import plotly.express as px

from services.backend_service import get_tabular

register_page(
    __name__,
    path="/sherlock/data-exploration/runtime-overview",
    title="HOLMES - Sherlock - Runtime Overview"
)

USAGE_BLOCKQUOTE_TEXT = [
    "Use Testrig Location and CCM Name filters to narrow the timeline.",
    "Last N days includes runs that ended recently and ongoing runs.",
    "Switch Runtime Component to show CCM, GDL, or PTL labels inside each bar.",
    "Hover bars for full run context and runtime details.",
]


def _resolve_runtime_component_column(df: pd.DataFrame, component: str) -> str:
    component_map = {
        "ccm": ["ccm_name"],
        "gdl": ["GDL_name", "gdl_name"],
        "ptl": ["PTL_name", "ptl_name"],
    }
    for candidate in component_map.get(component, ["ccm_name"]):
        if candidate in df.columns:
            return candidate
    return "ccm_name"


def _parse_days_selected(days_selected) -> int:
    try:
        days = int(float(days_selected))
    except (TypeError, ValueError):
        return 30
    return days if days > 0 else 30


def _normalize_location_value(raw_value: str) -> str:
    value = str(raw_value).strip()
    if not value:
        return "Unknown"
    # Some datasets encode location as '<testrig> - <location>'.
    if " - " in value:
        parts = [part.strip() for part in value.split(" - ") if part.strip()]
        if parts:
            return parts[-1]
    return value

def runtime_overview_layout():
    return dmc.Container(
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
                                    dmc.Title("Runtime Overview", order=2),
                                    dmc.ActionIcon(
                                        DashIconify(icon="material-symbols:info-outline", width=20),
                                        id="runtime-usage-toggle",
                                        variant="subtle",
                                        color="blue",
                                        size="md",
                                        radius="xl",
                                    ),
                                ],
                            ),
                            dmc.Text("Timeline view of stack-level runtime executions.", c="dimmed"),
                            dmc.Collapse(
                                dmc.Blockquote(
                                    dmc.List(
                                        withPadding=False,
                                        children=[dmc.ListItem(item) for item in USAGE_BLOCKQUOTE_TEXT],
                                    ),
                                    color="blue",
                                ),
                                opened=False,
                                id="runtime-usage-collapse",
                            ),
                        ],
                    ),
                    dcc.Store(id="runtime-usage-open", data=False),
                    dcc.Store(id="runtime-metadata-store"),
                    dcc.Store(id="ccm-data-store"),
                    dcc.Store(id="runtime-filtered-store"),
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
                                        dcc.Dropdown(
                                            id="runtime-location-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            placeholder="Select one or more locations",
                                            style={"width": "100%"},
                                        ),
                                        label="Location",
                                        htmlFor="runtime-location-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "0 1 280px", "minWidth": "230px", "maxWidth": "360px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="runtime-testrig-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            placeholder="Select testrig IDs",
                                            style={"width": "100%"},
                                        ),
                                        label="Testrig ID",
                                        htmlFor="runtime-testrig-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "1 1 auto", "minWidth": "420px"},
                                    ),
                                    dmc.Stack(
                                        gap=6,
                                        children=[
                                            dmc.Text("Last N days", size="sm", fw=600),
                                            dmc.NumberInput(
                                                id="last-n-days",
                                                value=30,
                                                min=1,
                                                step=1,
                                                style={"width": "160px"},
                                            ),
                                        ],
                                    ),
                                    dmc.Button(
                                        [
                                            html.I(className="bi bi-download", style={"marginRight": "10px", "fontSize": "1.1em"}),
                                            "Download CSV",
                                        ],
                                        id="ccm-download-btn",
                                        n_clicks=0,
                                        className="download-btn",
                                    ),
                                    dcc.Download(id="ccm-download-csv"),
                                ],
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
                                style={"flexWrap": "wrap"},
                                children=[
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="ccm-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            placeholder="Select CCM names",
                                            style={"width": "100%"},
                                        ),
                                        label="CCM",
                                        htmlFor="ccm-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "1", "minWidth": "260px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="gdl-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            placeholder="Select GDL names",
                                            style={"width": "100%"},
                                        ),
                                        label="GDL",
                                        htmlFor="gdl-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "1", "minWidth": "220px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="ptl-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            placeholder="Select PTL names",
                                            style={"width": "100%"},
                                        ),
                                        label="PTL",
                                        htmlFor="ptl-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "1", "minWidth": "220px"},
                                    ),
                                ],
                            ),
                            dmc.Space(h="sm"),
                            dmc.Divider(size="xs"),
                            dmc.Space(h="sm"),
                            dmc.Group(
                                justify="space-between",
                                align="center",
                                children=[
                                    dmc.Text(
                                        id="runtime-summary-text",
                                        c="dimmed",
                                        size="sm",
                                        children="Summary: 0 orders, 0.0 running hours",
                                    ),
                                    dmc.Group(
                                        gap="sm",
                                        align="center",
                                        children=[
                                            dmc.Text("Runtime Component", size="sm", c="dimmed", fw=600),
                                            dmc.SegmentedControl(
                                                id="runtime-component-selector",
                                                data=[
                                                    {"label": "CCM", "value": "ccm"},
                                                    {"label": "GDL", "value": "gdl"},
                                                    {"label": "PTL", "value": "ptl"},
                                                ],
                                                value="ccm",
                                                size="sm",
                                                radius="md",
                                                style={"minWidth": "210px"},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            dmc.Space(h="sm"),
                            dmc.Box(
                                pos="relative",
                                children=[
                                    dmc.LoadingOverlay(
                                        id="runtime-plot-loading-overlay",
                                        visible=True,
                                        zIndex=10,
                                        loaderProps={"color": "blue", "size": "lg", "variant": "dots"},
                                        overlayProps={"radius": "sm", "blur": 1},
                                    ),
                                    dmc.Box(
                                        id="runtime-plot-wrapper",
                                        style={
                                            "opacity": 0,
                                            "overflow": "hidden",
                                            "minHeight": "calc(100dvh - var(--app-shell-header-offset, 0rem) - 360px)",
                                            "maxHeight": "calc(100dvh - var(--app-shell-header-offset, 0rem) - 360px)",
                                        },
                                        children=[dcc.Graph(id="ccm-runtime-plot")],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            )
        ],
    )


layout = runtime_overview_layout


@callback(
    Output("runtime-usage-open", "data"),
    Input("runtime-usage-toggle", "n_clicks"),
    State("runtime-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage_blockquote(n_clicks, is_open):
    if n_clicks is None:
        return no_update
    return not bool(is_open)


@callback(
    Output("runtime-usage-collapse", "opened"),
    Input("runtime-usage-open", "data"),
)
def sync_usage_blockquote(is_open):
    return bool(is_open)

# Load runtime metadata once on page load
@callback(
    Output("runtime-metadata-store", "data"),
    Input("ccm-runtime-plot", "id"),  # Dummy input to trigger on page load
    prevent_initial_call=False,
)
def load_runtime_metadata(_):
    df = get_tabular("sherlock", "runtime")
    if df.empty:
        return []

    return df.to_dict("records")


def _normalize_runtime_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in ["start_time", "end_time"]:
        if col not in df.columns:
            continue
        numeric_ts = pd.to_numeric(df[col], errors="coerce")
        parsed_epoch = pd.to_datetime(numeric_ts, errors="coerce", unit="ms", utc=True)
        parsed_string = pd.to_datetime(df[col], errors="coerce", utc=True)
        df[col] = parsed_string.where(parsed_string.notna(), parsed_epoch)

    if "sample_id" in df.columns:
        # Only drop missing sample IDs when there are valid IDs to keep.
        valid_sample_mask = df["sample_id"].notna() & (df["sample_id"].astype(str).str.lower() != "null")
        if valid_sample_mask.any():
            df = df[valid_sample_mask]

    if "ccm_name" in df.columns:
        df["ccm_name"] = df["ccm_name"].fillna("Unknown")

    if "testrig_label" not in df.columns:
        df["testrig_label"] = "Unknown"

    if "ccm_name" not in df.columns:
        df["ccm_name"] = "Unknown"

    if "GDL_name" not in df.columns and "gdl_name" in df.columns:
        df["GDL_name"] = df["gdl_name"]
    if "PTL_name" not in df.columns and "ptl_name" in df.columns:
        df["PTL_name"] = df["ptl_name"]

    if "testrig_location" not in df.columns:
        if "location" in df.columns:
            df["testrig_location"] = df["location"]
        elif "testrig_label" in df.columns:
            df["testrig_location"] = df["testrig_label"]
        else:
            df["testrig_location"] = "Unknown"

    if "testrig_id" not in df.columns:
        if "testrig_label" in df.columns:
            df["testrig_id"] = df["testrig_label"].astype(str)
        else:
            df["testrig_id"] = "Unknown"

    df["testrig_location"] = df["testrig_location"].fillna("Unknown").astype(str)
    df["testrig_location"] = df["testrig_location"].map(_normalize_location_value)
    df["testrig_id"] = df["testrig_id"].fillna("Unknown").astype(str)
    df["ccm_name"] = df["ccm_name"].fillna("Unknown").astype(str)
    if "GDL_name" in df.columns:
        df["GDL_name"] = df["GDL_name"].fillna("Unknown").astype(str)
    if "PTL_name" in df.columns:
        df["PTL_name"] = df["PTL_name"].fillna("Unknown").astype(str)
    return df


@callback(
    Output("runtime-location-filter", "options"),
    Output("runtime-location-filter", "value"),
    Output("runtime-testrig-filter", "options"),
    Output("runtime-testrig-filter", "value"),
    Input("runtime-metadata-store", "data"),
    Input("runtime-location-filter", "value"),
    State("runtime-testrig-filter", "value"),
)
def populate_top_filters(meta_data, selected_locations, current_testrigs):
    if not meta_data:
        return [], [], [], []

    df = _normalize_runtime_dataframe(pd.DataFrame(meta_data))

    locations = sorted(df["testrig_location"].dropna().unique())
    location_options = [{"label": loc, "value": loc} for loc in locations]

    tbp_locations = [loc for loc in locations if "tbp" in str(loc).lower()]
    default_locations = tbp_locations or locations
    normalized_locations = selected_locations or default_locations

    if normalized_locations:
        df = df[df["testrig_location"].isin(normalized_locations)]

    testrigs = sorted(df["testrig_id"].dropna().astype(str).unique())
    testrig_options = [{"label": tr, "value": tr} for tr in testrigs]
    available_testrigs = set(testrigs)

    if current_testrigs:
        selected_testrigs = [str(tr) for tr in current_testrigs if str(tr) in available_testrigs]
    else:
        selected_testrigs = testrigs

    return location_options, normalized_locations, testrig_options, selected_testrigs


@callback(
    Output("ccm-data-store", "data"),
    Input("runtime-location-filter", "value"),
    Input("runtime-testrig-filter", "value"),
    prevent_initial_call=False,
)
def fetch_runtime_data(selected_locations, selected_testrigs):
    df = get_tabular("sherlock", "runtime")
    if df.empty:
        return []

    dff = _normalize_runtime_dataframe(df)

    if selected_locations:
        dff = dff[dff["testrig_location"].isin(selected_locations)]
    if selected_testrigs:
        dff = dff[dff["testrig_id"].isin([str(tr) for tr in selected_testrigs])]

    return dff.to_dict("records")


@callback(
    Output("ccm-filter", "options"),
    Output("ccm-filter", "value"),
    Output("gdl-filter", "options"),
    Output("gdl-filter", "value"),
    Output("ptl-filter", "options"),
    Output("ptl-filter", "value"),
    Input("ccm-data-store", "data"),
)
def populate_plot_filters(data):
    if not data:
        return [], [], [], [], [], []

    df = pd.DataFrame(data)

    ccm_values = sorted(df["ccm_name"].fillna("Unknown").astype(str).unique()) if "ccm_name" in df.columns else []
    gdl_values = sorted(df["GDL_name"].fillna("Unknown").astype(str).unique()) if "GDL_name" in df.columns else []
    ptl_values = sorted(df["PTL_name"].fillna("Unknown").astype(str).unique()) if "PTL_name" in df.columns else []

    ccm_options = [{"label": c, "value": c} for c in ccm_values]
    gdl_options = [{"label": g, "value": g} for g in gdl_values]
    ptl_options = [{"label": p, "value": p} for p in ptl_values]

    return ccm_options, ccm_values, gdl_options, gdl_values, ptl_options, ptl_values


clientside_callback(
    """
    function(data, ccmFilter, gdlFilter, ptlFilter, daysSelected) {
        if (!data || !data.length) {
            return [];
        }

        const days = (() => {
            const parsed = parseInt(daysSelected, 10);
            return Number.isFinite(parsed) && parsed > 0 ? parsed : 30;
        })();

        const now = new Date();
        const cutoff = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);

        return data.filter((row) => {
            const ccm = (row.ccm_name ?? "Unknown").toString();
            const gdl = (row.GDL_name ?? row.gdl_name ?? "Unknown").toString();
            const ptl = (row.PTL_name ?? row.ptl_name ?? "Unknown").toString();

            if (ccmFilter && ccmFilter.length && ccmFilter.indexOf(ccm) === -1) {
                return false;
            }
            if (gdlFilter && gdlFilter.length && gdlFilter.indexOf(gdl) === -1) {
                return false;
            }
            if (ptlFilter && ptlFilter.length && ptlFilter.indexOf(ptl) === -1) {
                return false;
            }

            const start = row.start_time ? new Date(row.start_time) : null;
            const end = row.end_time ? new Date(row.end_time) : now;

            const startValid = start && !isNaN(start.getTime()) ? start : cutoff;
            const endValid = end && !isNaN(end.getTime()) ? end : now;

            return endValid >= cutoff && startValid <= now;
        });
    }
    """,
    Output("runtime-filtered-store", "data"),
    Input("ccm-data-store", "data"),
    Input("ccm-filter", "value"),
    Input("gdl-filter", "value"),
    Input("ptl-filter", "value"),
    Input("last-n-days", "value"),
)


@callback(
    Output("runtime-plot-loading-overlay", "visible"),
    Output("runtime-plot-wrapper", "style"),
    Input("ccm-runtime-plot", "loading_state"),
    Input("runtime-filtered-store", "data"),
)
def sync_runtime_plot_loading(loading_state, filtered_data):
    loading = bool(loading_state and loading_state.get("is_loading"))
    data_ready = filtered_data is not None

    loading_style = {
        "opacity": 0,
        "overflow": "hidden",
        "minHeight": "calc(100dvh - var(--app-shell-header-offset, 0rem) - 360px)",
        "maxHeight": "calc(100dvh - var(--app-shell-header-offset, 0rem) - 360px)",
    }
    loaded_style = {
        "opacity": 1,
        "overflow": "visible",
        "minHeight": "0",
        "maxHeight": "none",
        "transition": "opacity 180ms ease",
    }

    if loading or not data_ready:
        return True, loading_style
    return False, loaded_style

# Main Gantt callback
@callback(
    Output("ccm-runtime-plot", "figure"),
    Output("runtime-summary-text", "children"),
    Input("runtime-filtered-store", "data"),
    Input("last-n-days", "value"),
    Input("runtime-component-selector", "value"),
    Input("theme-store", "data"),
)
def update_ccm_plot(filtered_data, days_selected, runtime_component, theme_store):
    if not filtered_data:
        return px.scatter(title=f"Runtime Overview (Last {_parse_days_selected(days_selected)} Days)"), "Summary: 0 orders, 0.0 running hours"

    df = _normalize_runtime_dataframe(pd.DataFrame(filtered_data))
    is_dark = theme_store == "dark"
    template = "plotly_dark" if is_dark else "plotly"
    font_color = "#ffffff" if is_dark else "#000000"

    dff = df.copy()

    # Compute the viewport window — used only for x-axis range, not row filtering.
    days = _parse_days_selected(days_selected)
    now_utc = pd.Timestamp.now(tz="UTC")
    cutoff = now_utc - pd.Timedelta(days=days)

    if dff.empty:
        return px.scatter(title=f"Runtime Overview (Last {days} Days)"), "Summary: 0 orders, 0.0 running hours"

    # Sort
    dff = dff.sort_values(
        by=["testrig_id", "order_id", "start_time"],
        ascending=[True, True, True],
    )

    # Keep only rows that overlap the visible window [cutoff, now_utc].
    eff_end = dff["end_time"].fillna(now_utc) if "end_time" in dff.columns else now_utc
    eff_start = dff["start_time"].fillna(cutoff) if "start_time" in dff.columns else cutoff
    visible_mask = (eff_end >= cutoff) & (eff_start <= now_utc)
    dff_plot = dff[visible_mask].copy()

    if dff_plot.empty:
        return px.scatter(title=f"Runtime Overview (Last {days} Days)"), "Summary: 0 orders, 0.0 running hours"

    dff_plot["order_id"] = pd.Categorical(
        dff_plot["order_id"],
        categories=dff_plot["order_id"].unique(),
        ordered=True,
    )

    # Text fields
    runtime_component = runtime_component if runtime_component in {"ccm", "gdl", "ptl"} else "ccm"
    component_col = _resolve_runtime_component_column(dff_plot, runtime_component)
    dff_plot["bar_text"] = dff_plot[component_col].fillna("Unknown")
    dff_plot["total_runtime_hours"] = dff_plot["total_runtime"].round(2)
    dff_plot["right_label"] = dff_plot["total_runtime_hours"].map(lambda x: f"{x:.2f} h")
    dff_plot["start_time_fmt"] = dff_plot["start_time"].dt.strftime("%Y-%m-%d %H:%M")
    dff_plot["end_time_fmt"] = dff_plot["end_time"].dt.strftime("%Y-%m-%d %H:%M")
    dff_plot["end_time_fmt"] = dff_plot["end_time_fmt"].fillna("Ongoing")

    # Plot clipped segments so text is centered in the visible portion of each bar.
    dff_plot["plot_start_time"] = dff_plot["start_time"].where(dff_plot["start_time"] >= cutoff, cutoff)
    dff_plot["plot_end_time"] = dff_plot["end_time"].fillna(now_utc)
    dff_plot["plot_end_time"] = dff_plot["plot_end_time"].where(dff_plot["plot_end_time"] <= now_utc, now_utc)
    dff_plot["bar_mid_time"] = dff_plot["plot_start_time"] + (
        (dff_plot["plot_end_time"] - dff_plot["plot_start_time"]) / 2
    )

    total_orders = int(dff_plot["order_id"].nunique()) if "order_id" in dff_plot.columns else 0
    total_rigs = int(dff_plot["testrig_id"].nunique()) if "testrig_id" in dff_plot.columns else 0
    active_hours = 0.0
    if total_rigs > 0:
        for _, rig_df in dff_plot.groupby("testrig_id", observed=True):
            rig_intervals = (
                rig_df[["plot_start_time", "plot_end_time"]]
                .dropna()
                .sort_values("plot_start_time")
                .itertuples(index=False)
            )
            merged_start = None
            merged_end = None
            rig_active = 0.0
            for start, end in rig_intervals:
                if merged_start is None:
                    merged_start, merged_end = start, end
                    continue
                if start <= merged_end:
                    if end > merged_end:
                        merged_end = end
                else:
                    rig_active += (merged_end - merged_start).total_seconds() / 3600
                    merged_start, merged_end = start, end
            if merged_start is not None and merged_end is not None:
                rig_active += (merged_end - merged_start).total_seconds() / 3600
            active_hours += max(rig_active, 0.0)

    capacity_hours = max(total_rigs * days * 24, 0)
    efficiency_pct = (active_hours / capacity_hours * 100) if capacity_hours else 0.0
    summary_text = (
        f"Summary: {total_orders} orders, {active_hours:,.1f} running hours, "
        f"{efficiency_pct:.1f}% efficiency"
    )

    # Build Gantt
    fig = px.timeline(
        dff_plot,
        x_start="plot_start_time",
        x_end="plot_end_time",
        y="testrig_label",
        color="testrig_label",
        text="bar_text",
        custom_data=[
            "testrig_label",
            "order_id",
            "sample_id",
            "ccm_name",
            "PTL_name",
            "GDL_name",
            "bar_text",
            "active_area_per_cell",
            "total_runtime_hours",
            "start_time_fmt",
            "end_time_fmt",
        ],
        title=f"Runtime Overview (Last {days} Days)",
        template=template,
    )

    fig.update_traces(
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(color="white"),
        cliponaxis=False,
    )

    fig.update_traces(
        hovertemplate=
        "<b>Testrig Location:</b> %{customdata[0]}<br>"
        "<b>Order ID:</b> %{customdata[1]}<br>"
        "<b>Sample ID:</b> %{customdata[2]}<br>"
        "<b>CCM Name:</b> %{customdata[3]}<br>"
        "<b>PTL Name:</b> %{customdata[4]}<br>"
        "<b>GDL Name:</b> %{customdata[5]}<br>"
        "<b>Selected Label:</b> %{customdata[6]}<br>"
        "<b>Active Area per Cell:</b> %{customdata[7]}<br>"
        "<b>Total Run Time (hours):</b> %{customdata[8]:.2f} h<br>"
        "<b>Start Date:</b> %{customdata[9]}<br>"
        "<b>End Date:</b> %{customdata[10]}"
        "<extra></extra>"
    )

    right_padding = pd.Timedelta(hours=min(72, max(12, days * 4)))
    x_range_end = now_utc + right_padding

    for row in dff_plot.itertuples(index=False):
        fig.add_annotation(
            x=row.bar_mid_time,
            y=row.testrig_label,
            text=row.right_label,
            showarrow=False,
            yshift=14,
            font={"size": 10, "color": font_color},
            xanchor="center",
            yanchor="bottom",
        )

    fig.update_yaxes(
        autorange="reversed",
        title="Test Rig",
        categoryorder="array",
        categoryarray=dff_plot["testrig_label"].astype(str).unique(),
    )

    fig.update_xaxes(
        title="Time",
        showgrid=True,
        # Clip the view to the last N days — bars that extend outside remain
        # in the dataset (for download) but are cropped by the axis range.
        range=[cutoff, x_range_end],
    )

    n_rows = dff_plot["testrig_label"].nunique()
    bar_height_px = 40  # px per y-axis category
    chart_height = max(500, n_rows * bar_height_px + 200)  # 200px headroom for title/legend/axes

    fig.update_layout(
        height=chart_height,
        font=dict(color=font_color),
        legend_title="Testrig Location",
        hoverlabel=dict(align="left"),
        bargap=0.3,
    )

    fig.add_vline(
        x=pd.Timestamp.utcnow(),
        line_width=2,
        line_dash="dot",
        line_color="red",
        layer="below",
    )

    return fig, summary_text

# Download callback
@callback(
    Output("ccm-download-csv", "data"),
    Input("ccm-download-btn", "n_clicks"),
    State("runtime-filtered-store", "data"),
    State("last-n-days", "value"),
    prevent_initial_call=True,
)
def download_ccm_table(n_clicks, table_data, days_selected):
    if not table_data:
        return no_update
    days = _parse_days_selected(days_selected)
    df_filtered = pd.DataFrame(table_data)
    return send_data_frame(
        df_filtered.to_csv,
        f"runtime_overview_last_{days}_days.csv",
        index=False,
    )