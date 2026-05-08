from dash import dcc, callback, Output, Input, State, register_page
import dash_mantine_components as dmc
import dash_leaflet as dl
from dash_iconify import DashIconify
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from services.backend_service import get_tabular

register_page(
    __name__,
    path="/enola/customer/customer-overview",
    title="HOLMES - Enola - Customer Overview",
    name="HOLMES - Enola - Customer Overview",
)

USAGE_BLOCKQUOTE_TEXT = [
    "This dashboard provides an overview of deployed stacks per customer.",
    "KPI cards summarize active, commissioning, installed power, and stacks with exceeded warranty.",
    "The map shows geographical stack deployment using city coordinates.",
    "The lifecycle chart displays stack status distribution.",
    "The runtime chart compares total operational hours per customer.",
]

LIFECYCLE_COLORS = {
    "In Shipping - Arrival At Customer": "#2ca02c",
    "Installation - System FAT": "#1f77b4",
    "In Warranty Period": "#ff7f0e",
    "Warranty/Service Extension Exceeded": "#d62728",
    "Decommissioned": "#7f7f7f",
}

COMMISSIONING_STATUSES = ["In Shipping - Arrival At Customer", "Installation - System FAT"]
POWER_STATUSES = ["Installation - System FAT", "In Warranty Period"]
WARRANTY_EXCEEDED_STATUS = "Warranty/Service Extension Exceeded"

LIGHT_TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
DARK_TILE_URL = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'


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
                # ── Header ──────────────────────────────────────────
                dmc.Stack(
                    gap=2,
                    children=[
                        dmc.Group(
                            gap="xs",
                            align="center",
                            children=[
                                dmc.Title("Customer Overview", order=2),
                                dmc.ActionIcon(
                                    DashIconify(icon="material-symbols:info-outline", width=20),
                                    id="cust-usage-toggle",
                                    variant="subtle",
                                    color="blue",
                                    size="md",
                                    radius="xl",
                                ),
                            ],
                        ),
                        dmc.Text(
                            "Deployed stack portfolio — geographical distribution, lifecycle status, and runtime per customer.",
                            c="dimmed",
                        ),
                        dmc.Collapse(
                            dmc.Blockquote(
                                dmc.List(
                                    withPadding=False,
                                    children=[dmc.ListItem(t) for t in USAGE_BLOCKQUOTE_TEXT],
                                ),
                                color="blue",
                            ),
                            id="cust-usage-collapse",
                            opened=False,
                        ),
                    ],
                ),
                dcc.Store(id="cust-usage-open", data=False),
                dcc.Store(id="cust-data-store"),

                # ── KPI Cards ────────────────────────────────────────
                dmc.SimpleGrid(
                    cols=4,
                    spacing="md",
                    children=[
                        dmc.Paper(
                            withBorder=True, p="md", radius="md",
                            children=[
                                dmc.Text("Active Stacks", c="dimmed", size="sm"),
                                dmc.Title(id="cust-kpi-active", order=2),
                            ],
                        ),
                        dmc.Paper(
                            withBorder=True, p="md", radius="md",
                            children=[
                                dmc.Text("Commissioning", c="dimmed", size="sm"),
                                dmc.Title(id="cust-kpi-commissioning", order=2),
                            ],
                        ),
                        dmc.Paper(
                            withBorder=True, p="md", radius="md",
                            children=[
                                dmc.Text("Total Installed Power", c="dimmed", size="sm"),
                                dmc.Title(id="cust-kpi-power", order=2),
                            ],
                        ),
                        dmc.Paper(
                            withBorder=True, p="md", radius="md",
                            style={"borderColor": "var(--mantine-color-red-5)"},
                            children=[
                                dmc.Text("Warranty/Service Exceeded", c="dimmed", size="sm"),
                                dmc.Title(id="cust-kpi-warranty", order=2, c="red"),
                            ],
                        ),
                    ],
                ),

                # ── Map + Pie ────────────────────────────────────────
                dmc.Box(
                    style={
                        "flex": "1 1 0",
                        "minHeight": 0,
                        "display": "grid",
                        "gridTemplateColumns": "minmax(0, 1.8fr) minmax(320px, 1fr)",
                        "gap": "16px",
                        "overflow": "hidden",
                    },
                    children=[
                        dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="md",
                            style={
                                "height": "100%",
                                "minHeight": 0,
                                "display": "flex",
                                "flexDirection": "column",
                                "overflow": "hidden",
                            },
                            children=[
                                dmc.Group(
                                    justify="space-between",
                                    align="center",
                                    mb="sm",
                                    wrap="wrap",
                                    children=[
                                        dmc.Stack(
                                            gap=2,
                                            children=[
                                                dmc.Text("Global Stack Deployment", fw=600, size="sm"),
                                                dmc.Text(
                                                    "Bubble colors correspond to lifecycle categories shown in the pie chart.",
                                                    size="xs",
                                                    c="dimmed",
                                                ),
                                            ],
                                        ),
                                        dmc.Group(
                                            gap="xs",
                                            align="center",
                                            children=[
                                                dmc.Text("Bubble size", size="sm", fw=600),
                                                dmc.SegmentedControl(
                                                    id="cust-map-size-metric",
                                                    value="count",
                                                    data=[
                                                        {"label": "Stacks", "value": "count"},
                                                        {"label": "Power", "value": "installed_power_mw"},
                                                        {"label": "Runtime", "value": "max_runtime"},
                                                    ],
                                                    size="xs",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                dmc.Box(
                                    style={"flex": "1 1 0", "minHeight": 0},
                                    children=dl.Map(
                                        id="cust-leaflet-map",
                                        center=[20, 10],
                                        zoom=1.2,
                                        zoomSnap=0.1,
                                        zoomDelta=0.1,
                                        children=[
                                            dl.TileLayer(
                                                id="cust-map-tiles",
                                                url=LIGHT_TILE_URL,
                                                attribution=TILE_ATTRIBUTION,
                                            ),
                                            dl.LayerGroup(id="cust-map-markers"),
                                        ],
                                        style={"height": "100%", "borderRadius": "6px"},
                                    ),
                                ),
                            ],
                        ),
                        dmc.Paper(
                            withBorder=True,
                            p=0,
                            radius="md",
                            style={
                                "height": "100%",
                                "minHeight": 0,
                                "display": "flex",
                                "overflow": "hidden",
                            },
                            children=dcc.Graph(
                                id="cust-lifecycle-graph",
                                config={"responsive": True},
                                style={"height": "100%", "width": "100%", "flex": "1 1 auto", "minHeight": 0},
                            ),
                        ),
                    ],
                ),
            ],
        )
    ],
)


@callback(
    Output("cust-usage-open", "data"),
    Input("cust-usage-toggle", "n_clicks"),
    State("cust-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage(_, is_open):
    return not bool(is_open)


@callback(
    Output("cust-usage-collapse", "opened"),
    Input("cust-usage-open", "data"),
)
def sync_usage_collapse(is_open):
    return bool(is_open)


@callback(
    Output("cust-map-tiles", "url"),
    Output("cust-map-tiles", "attribution"),
    Input("theme-store", "data"),
)
def update_map_theme(theme):
    tile_url = DARK_TILE_URL if theme == "dark" else LIGHT_TILE_URL
    return tile_url, TILE_ATTRIBUTION


@callback(
    Output("cust-data-store", "data"),
    Input("cust-lifecycle-graph", "id"),
)
def load_data(_):
    try:
        df = get_tabular("enola", "customer")
    except Exception:
        return []
    return df.to_dict("records")


@callback(
    Output("cust-kpi-active", "children"),
    Output("cust-kpi-commissioning", "children"),
    Output("cust-kpi-power", "children"),
    Output("cust-kpi-warranty", "children"),
    Input("cust-data-store", "data"),
)
def update_kpis(data):
    if not data:
        return "—", "—", "—", "—"
    df = pd.DataFrame(data)
    active = 0
    commissioning = len(df[df["lifecycle_status"].isin(COMMISSIONING_STATUSES)]) if "lifecycle_status" in df.columns else 0
    power = 0.0
    if "lifecycle_status" in df.columns and "installed_power_mw" in df.columns:
        power = pd.to_numeric(
            df[df["lifecycle_status"].isin(POWER_STATUSES)]["installed_power_mw"], errors="coerce"
        ).sum()
    warranty_exc = len(df[df["lifecycle_status"] == WARRANTY_EXCEEDED_STATUS]) if "lifecycle_status" in df.columns else 0
    return str(active), str(commissioning), f"{power:.1f} MW", str(warranty_exc)


@callback(
    Output("cust-map-markers", "children"),
    Input("cust-data-store", "data"),
    Input("cust-map-size-metric", "value"),
)
def update_map(data, size_metric):
    if not data:
        return []
    df = pd.DataFrame(data)
    if not {"latitude", "longitude", "lifecycle_status"}.issubset(df.columns):
        return []
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    if "installed_power_mw" in df.columns:
        df["installed_power_mw"] = pd.to_numeric(df["installed_power_mw"], errors="coerce").fillna(0)
    if "max_runtime" in df.columns:
        df["max_runtime"] = pd.to_numeric(df["max_runtime"], errors="coerce").fillna(0)
    df = df.dropna(subset=["latitude", "longitude"])
    if df.empty:
        return []

    group_cols = [c for c in ("end_customer_city", "customer_country", "lifecycle_status", "latitude", "longitude") if c in df.columns]
    agg_dict = {"count": ("lifecycle_status", "count")}
    if "installed_power_mw" in df.columns:
        agg_dict["installed_power_mw"] = ("installed_power_mw", "sum")
    if "max_runtime" in df.columns:
        agg_dict["max_runtime"] = ("max_runtime", "sum")
    agg_df = df.groupby(group_cols, as_index=False).agg(**agg_dict)

    metric_col = size_metric if size_metric in agg_df.columns else "count"
    max_metric = pd.to_numeric(agg_df[metric_col], errors="coerce").fillna(0).max()

    def marker_radius(value):
        if max_metric <= 0:
            return 8
        return 6 + 16 * (float(value) / float(max_metric))

    markers = []
    for _, row in agg_df.iterrows():
        status = row.get("lifecycle_status", "Unknown")
        color = LIFECYCLE_COLORS.get(status, "#636EFA")
        city = row.get("end_customer_city", "Unknown")
        country = row.get("customer_country", "")
        count = int(row.get("count", 1))
        metric_value = float(row.get(metric_col, 0) or 0)

        if metric_col == "installed_power_mw":
            metric_text = f"Power: {metric_value:.2f} MW"
        elif metric_col == "max_runtime":
            metric_text = f"Runtime: {metric_value:.0f} h"
        else:
            metric_text = f"Stacks: {int(metric_value)}"

        markers.append(
            dl.CircleMarker(
                center=[row["latitude"], row["longitude"]],
                radius=marker_radius(metric_value),
                color="white",
                weight=1,
                fillColor=color,
                fillOpacity=0.8,
                children=dl.Tooltip(f"{city}, {country} | {status} | Stacks: {count} | {metric_text}"),
            )
        )
    return markers


@callback(
    Output("cust-lifecycle-graph", "figure"),
    Input("cust-data-store", "data"),
    Input("theme-store", "data"),
)
def update_charts(data, theme):
    template = "plotly_dark" if theme == "dark" else "plotly"
    empty_fig = go.Figure()
    empty_fig.update_layout(template=template)
    if not data:
        return empty_fig

    df = pd.DataFrame(data)

    if "lifecycle_status" in df.columns:
        lifecycle_data = df.groupby("lifecycle_status").size().reset_index(name="count")
        lifecycle_fig = px.pie(
            lifecycle_data, names="lifecycle_status", values="count",
            title="Stack Lifecycle Status", hole=0.3, template=template,
            color="lifecycle_status", color_discrete_map=LIFECYCLE_COLORS,
        )
        lifecycle_fig.update_layout(
            margin=dict(l=20, r=20, t=48, b=38),
            legend=dict(
                orientation="h",
                x=0.5,
                xanchor="center",
                y=-0.06,
                yanchor="top",
                title=None,
            ),
        )
    else:
        lifecycle_fig = empty_fig

    return lifecycle_fig