from dash import html, dcc, callback, Output, Input, State, register_page, no_update
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
                                opened=True,
                                id="runtime-usage-collapse",
                            ),
                        ],
                    ),
                    dcc.Store(id="runtime-usage-open", data=True),
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
                                            id="testrig-location-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            placeholder="Select one or more locations",
                                            style={"width": "100%"},
                                        ),
                                        label="Filter by Testrig Location",
                                        htmlFor="testrig-location-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "1", "minWidth": "280px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="ccm-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            placeholder="Select CCM names",
                                            style={"width": "360px"},
                                        ),
                                        label="Filter by CCM Name",
                                        htmlFor="ccm-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
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
                            dcc.Loading(
                                id="ccm-runtime-loading",
                                children=[dcc.Graph(id="ccm-runtime-plot")],
                                type="default",
                            )
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

# Load data and populate dropdowns/table columns
@callback(
    Output("ccm-data-store", "data"),
    Output("testrig-location-filter", "options"),
    Output("ccm-filter", "options"),
    Output("testrig-location-filter", "value"),
    Output("ccm-filter", "value"),
    Input("ccm-runtime-plot", "id"),  # Dummy input to trigger on page load
    prevent_initial_call=False,
)
def load_ccm_data(_):
    df = get_tabular("sherlock", "ccm")
    if df.empty:
        return [], [], [], [], []

    for col in ["start_time", "end_time"]:
        if col not in df.columns:
            continue
        # Support both epoch milliseconds and ISO timestamp strings.
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

    testrig_options = [
        {"label": x, "value": x}
        for x in sorted(df["testrig_label"].dropna().unique())
    ]
    ccm_options = [
        {"label": c, "value": c}
        for c in sorted(df["ccm_name"].unique())
    ]

    # Set default values to show all options
    testrig_values = [x["value"] for x in testrig_options]
    ccm_values = [x["value"] for x in ccm_options]

    return df.to_dict("records"), testrig_options, ccm_options, testrig_values, ccm_values

# Main Gantt callback
@callback(
    Output("ccm-runtime-plot", "figure"),
    Output("runtime-filtered-store", "data"),
    Output("runtime-summary-text", "children"),
    Input("ccm-filter", "value"),
    Input("testrig-location-filter", "value"),
    Input("last-n-days", "value"),
    Input("runtime-component-selector", "value"),
    Input("theme-store", "data"),
    State("ccm-data-store", "data"),
)
def update_ccm_plot(ccm_filter, testrig_location_filter, days_selected, runtime_component, theme_store, data_store):
    if not data_store:
        return no_update, no_update, "Summary: no data loaded"

    df = pd.DataFrame(data_store)
    for col in ["start_time", "end_time"]:
        if col not in df.columns:
            continue
        # Two-step parse: first generic parse, then localize/convert to UTC.
        # Using utc=True alone can silently produce NaT for some string formats
        # that Dash emits when serialising Timestamps through dcc.Store JSON.
        parsed = pd.to_datetime(df[col], errors="coerce")
        if parsed.dt.tz is None:
            df[col] = parsed.dt.tz_localize("UTC")
        else:
            df[col] = parsed.dt.tz_convert("UTC")
    is_dark = theme_store == "dark"
    template = "plotly_dark" if is_dark else "plotly"
    font_color = "#ffffff" if is_dark else "#000000"

    dff = df.copy()

    # Compute the viewport window — used only for x-axis range, not row filtering.
    days = _parse_days_selected(days_selected)
    now_utc = pd.Timestamp.now(tz="UTC")
    cutoff = now_utc - pd.Timedelta(days=days)

    if dff.empty:
        return px.scatter(title=f"Runtime Overview (Last {days} Days)"), [], "Summary: 0 orders, 0.0 running hours"

    # CCM filter
    if ccm_filter:
        dff = dff[dff["ccm_name"].isin(ccm_filter)]

    # Testrig location filter
    if testrig_location_filter:
        dff = dff[dff["testrig_label"].isin(testrig_location_filter)]

    if dff.empty:
        return px.scatter(title=f"Runtime Overview (Last {days} Days)"), [], "Summary: 0 orders, 0.0 running hours"

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
        return px.scatter(title=f"Runtime Overview (Last {days} Days)"), dff.to_dict("records"), "Summary: 0 orders, 0.0 running hours"

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

    total_orders = int(dff_plot["order_id"].nunique()) if "order_id" in dff_plot.columns else 0
    # Match what is visually perceived as one bar per order row by aggregating
    # the visible window span across all segments for each order_id.
    order_window = (
        dff_plot.groupby("order_id", observed=True)
        .agg(plot_start_time=("plot_start_time", "min"), plot_end_time=("plot_end_time", "max"))
        .reset_index()
    )
    visible_hours = (
        (order_window["plot_end_time"] - order_window["plot_start_time"])
        .dt.total_seconds()
        .div(3600)
        .clip(lower=0)
        .sum()
    )
    summary_text = f"Summary: {total_orders} orders, {visible_hours:,.1f} running hours"

    # Build Gantt
    fig = px.timeline(
        dff_plot,
        x_start="plot_start_time",
        x_end="plot_end_time",
        y="order_id",
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

    for rig in dff_plot["testrig_label"].dropna().unique():
        rig_df = dff_plot[dff_plot["testrig_label"] == rig]
        fig.add_scatter(
            x=rig_df["plot_end_time"],
            y=rig_df["order_id"],
            text=" " + rig_df["right_label"],
            mode="text",
            textposition="middle right",
            legendgroup=str(rig),
            showlegend=False,
            hoverinfo="skip",
        )

    fig.update_yaxes(
        autorange="reversed",
        title="Order ID",
        categoryorder="array",
        categoryarray=dff_plot["order_id"].astype(str).unique(),
    )

    fig.update_xaxes(
        title="Time",
        showgrid=True,
        # Clip the view to the last N days — bars that extend outside remain
        # in the dataset (for download) but are cropped by the axis range.
        range=[cutoff, x_range_end],
    )

    n_rows = dff_plot["order_id"].nunique()
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

    return fig, dff.to_dict("records"), summary_text

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