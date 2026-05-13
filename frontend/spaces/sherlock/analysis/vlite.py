from dash import (
    dcc,
    callback,
    Output,
    Input,
    State,
    register_page,
    no_update,
    html,
    clientside_callback,
)
from dash.exceptions import PreventUpdate
from dash.dcc.express import send_data_frame
import dash_mantine_components as dmc
import dash_ag_grid as dag
import pandas as pd
import plotly.graph_objects as go
from dash_iconify import DashIconify

from services.backend_service import get_metadata, get_tabular
from services.vlite_service import FitFix, run_model as vlite_run_model

register_page(
    __name__, path="/sherlock/data-analysis/vlite", title="HOLMES - Sherlock - V-Lite"
)

# ── Constants ──────────────────────────────────────────────────────────────────

USAGE_BLOCKQUOTE_TEXT = [
    "Select an Order ID to load polarisation curve data for that order.",
    "Select one or more events from the Event ID(s) dropdown, then click 'Run Model' to fit the V-lite model.",
    "When an input parameter is missing or zero, it is highlighted in red in the parameter table. A standard value is used for the model.",
    "After the model runs, select an event in the Results section to see the loss stackup and temperature increase plots.",
    "Download the polcurve data and model results as CSV using the Download CSV button.",
]

PARAM_KEYS = [
    "OCVE00", "OCVee", "OCVTref", "OCVpref",
    "memT0", "memSigLa", "memSig0",
    "CCMG", "CCMj00", "CCMnval", "lambda_val", "ICRress",
    "LSQerravg",
]

PARAM_DISPLAY_NAMES = {
    "LSQerravg": "LSQres [mV]",
}

# FitFix params (ICRress, CCMj00, CCMnval have fitfix=1 in vlite_service.FitFix)
PARAM_FITTED = {"CCMj00", "CCMnval", "ICRress"}

# Metadata columns required by the model — highlighted red when missing/zero/NaN
METADATA_CRITICAL_COLUMNS = {"number_of_cells", "active_area_per_cell", "ccm_thickness"}

METADATA_DISPLAY_COLUMNS = [
    "order_id", "name", "testrig_id", "number_of_cells",
    "active_area_per_cell", "ccm_thickness", "ccm_name",
]

METADATA_COLUMN_WIDTHS = {
    "order_id": 130, "name": 170, "testrig_id": 120,
    "number_of_cells": 120, "active_area_per_cell": 210,
    "ccm_thickness": 130, "ccm_name": 170,
}

METADATA_COLUMN_LABELS = {
    "order_id": "Order ID",
    "name": "Sample Name",
    "testrig_id": "Testrig",
    "number_of_cells": "Cells",
    "active_area_per_cell": "Active Area / Cell [cm²]",
    "ccm_thickness": "CCM Thk. [µm]",
    "ccm_name": "CCM Name",
}

_TRACE_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    "#bcbd22", "#17becf",
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def _blank_figure(theme: str | None = None) -> go.Figure:
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    return go.Figure(layout=go.Layout(template=template, margin=dict(l=40, r=20, t=30, b=40)))


def _add_event_short_id(df: pd.DataFrame) -> pd.DataFrame:
    """Add event_short_id column if not present, matching vlite_service.PolcurveData."""
    if "event_short_id" not in df.columns and "event_id" in df.columns and "order_id" in df.columns:
        df = df.copy()
        df["event_short_id"] = df.apply(
            lambda row: f"{row['order_id']}_{str(row['event_id']).split('_')[-1]}", axis=1
        )
    return df


def _fmt_param(val) -> str:
    if isinstance(val, float):
        if abs(val) >= 1e4 or (val != 0 and abs(val) < 1e-3):
            return f"{val:.3e}"
        return f"{val:.4f}"
    return str(val)


_CELL_STYLE_INVALID = (
    "params.value == null || params.value === 0 || params.value === '' || "
    "(typeof params.value === 'number' && isNaN(params.value)) "
    "? {'color': 'var(--mantine-color-red-6)', 'fontWeight': '700'} : {}"
)


def _metadata_column_def(col: str) -> dict:
    col_def = {
        "headerName": METADATA_COLUMN_LABELS.get(col, col),
        "field": col,
        "width": METADATA_COLUMN_WIDTHS.get(col, 120),
        "wrapHeaderText": True,
        "autoHeaderHeight": True,
        "sortable": False,
        "filter": False,
    }
    if col == "active_area_per_cell":
        col_def["valueFormatter"] = {
            "function": "params.value == null ? '' : Number(params.value).toFixed(3)"
        }
    if col in METADATA_CRITICAL_COLUMNS:
        col_def["cellStyle"] = {"function": _CELL_STYLE_INVALID}
    return col_def


# ── Layout ─────────────────────────────────────────────────────────────────────

def vlite_layout():
    return dmc.Container(
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
                    # ── Title section ───────────────────────────────────────────
                    dmc.Stack(
                        gap=2,
                        children=[
                            dmc.Group(
                                gap="xs",
                                align="center",
                                children=[
                                    dmc.Title("Polcurve Analysis: V-lite", order=2),
                                    dmc.ActionIcon(
                                        DashIconify(
                                            icon="material-symbols:info-outline",
                                            width=20,
                                        ),
                                        id="vlite-usage-toggle",
                                        variant="subtle",
                                        color="blue",
                                        size="md",
                                        radius="xl",
                                    ),
                                ],
                            ),
                            dmc.Text(
                                html.P([
                                    "Analysis of polcurve data using the",
                                    html.A(
                                        " v-lite model",
                                        href="https://inside-docupedia.bosch.com/confluence/spaces/ELYSTACK/pages/6183464450/V-Lite",
                                        target="_blank",
                                        style={"textDecoration": "underline"},
                                    ),
                                    " version 1.3.",
                                ]),
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
                                id="vlite-usage-collapse",
                            ),
                        ],
                    ),

                    # ── Single main container with all content ──────────────────
                    dmc.Paper(
                        withBorder=True,
                        p="md",
                        radius="md",
                        style={
                            "flex": "1 1 0",
                            "minHeight": 0,
                            "display": "flex",
                            "flexDirection": "column",
                            "overflow": "hidden",
                        },
                        children=[
                            # ── Filter section ──────────────────────────────────
                            dmc.Group(
                                gap="md",
                                align="flex-end",
                                style={
                                    "flexWrap": "nowrap",
                                    "overflowX": "auto",
                                    "overflowY": "hidden",
                                },
                                children=[
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="vlite-order-id-filter",
                                            multi=False,
                                            placeholder="Order ID",
                                            className="dmc",
                                            style={"width": "100%"},
                                        ),
                                        label="Order ID",
                                        htmlFor="vlite-order-id-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": 1, "minWidth": "200px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="vlite-event-id-filter",
                                            multi=True,
                                            placeholder="Event(s)",
                                            className="dmc",
                                            style={"width": "100%"},
                                        ),
                                        label="Event ID(s)",
                                        htmlFor="vlite-event-id-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": 2, "minWidth": "320px"},
                                    ),
                                    dmc.Button(
                                        "Run Model",
                                        id="vlite-run-model-btn",
                                        n_clicks=0,
                                        style={"flex": "0 0 auto", "whiteSpace": "nowrap"},
                                    ),
                                    dmc.Button(
                                        [
                                            html.I(
                                                className="bi bi-download",
                                                style={"marginRight": "10px", "fontSize": "1.1em"},
                                            ),
                                            "Download CSV",
                                        ],
                                        id="vlite-download-btn",
                                        n_clicks=0,
                                        className="download-btn",
                                        disabled=True,
                                        style={"flex": "0 0 auto", "whiteSpace": "nowrap"},
                                    ),
                                ],
                            ),
                            dcc.Download(id="vlite-download-csv"),
                            dmc.Space(h="sm"),
                            
                            dmc.Divider(size="xs", my="sm"),

                            # ── Content sections ────────────────────────────────
                            dmc.Box(
                                style={
                                    "display": "flex",
                                    "flexDirection": "column",
                                    "flex": "1 1 0",
                                    "minHeight": 0,
                                    "gap": "16px",
                                    "overflow": "auto",
                                },
                                children=[
                                    # Section 1: Polcurve + Model Fit + Metadata
                                    dmc.Stack(
                                        gap="sm",
                                        children=[
                                            dmc.Text("Polcurve + Model Fit", fw=600, size="sm"),
                                            dmc.Text(id="vlite-model-status", c="dimmed", size="sm"),
                                            dcc.Graph(
                                                id="vlite-polcurve-plot",
                                                style={"height": 420},
                                            ),
                                            dmc.Divider(size="xs", my="sm"),
                                            dmc.Text("Order Metadata", fw=600, size="sm"),
                                            dag.AgGrid(
                                                id="vlite-metadata-table",
                                                columnDefs=[],
                                                rowData=[],
                                                defaultColDef={
                                                    "resizable": True,
                                                    "sortable": True,
                                                    "filter": True,
                                                    "minWidth": 40,
                                                    "wrapHeaderText": True,
                                                    "autoHeaderHeight": True,
                                                },
                                                dashGridOptions={
                                                    "pagination": False,
                                                    "domLayout": "normal",
                                                    "rowHeight": 34,
                                                    "headerHeight": 34,
                                                },
                                                style={"height": "72px", "width": "100%"},
                                            ),
                                        ],
                                    ),

                                    dmc.Divider(size="xs"),

                                    # Section 2: Model Results Plots
                                    dmc.Stack(
                                        gap="sm",
                                        children=[
                                            dmc.Text("Polcurve Model Results Plots", fw=600, size="sm"),
                                            dcc.Dropdown(
                                                id="vlite-stackup-event-dropdown",
                                                multi=False,
                                                placeholder="Select event for detailed plots",
                                                className="dmc",
                                                style={"width": "100%"},
                                            ),
                                            dmc.SimpleGrid(
                                                cols=2,
                                                spacing="md",
                                                children=[
                                                    dmc.Stack(
                                                        gap="sm",
                                                        children=[
                                                            dmc.Text("Loss Stackup", fw=600, size="xs"),
                                                            dcc.Graph(
                                                                id="vlite-stackup-plot",
                                                                style={"height": 395},
                                                            ),
                                                        ],
                                                    ),
                                                    dmc.Stack(
                                                        gap="sm",
                                                        children=[
                                                            dmc.Text("Water temperature increase", fw=600, size="xs"),
                                                            dcc.Graph(
                                                                id="vlite-dtw-plot",
                                                                style={"height": 395},
                                                            ),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),

                                    dmc.Divider(size="xs"),

                                    # Section 3: Model Parameters
                                    dmc.Stack(
                                        gap="sm",
                                        children=[
                                            dmc.Text("Model Parameters", fw=600, size="sm"),
                                            html.Div(id="vlite-parameter-table"),
                                        ],
                                    ),
                                ],
                            ),

                            # ── Stores ──────────────────────────────────────────
                            dcc.Store(id="vlite-metadata-store"),
                            dcc.Store(id="vlite-data-store"),
                            dcc.Store(id="vlite-model-store"),
                            dcc.Store(id="vlite-usage-open", data=False),
                            dcc.Store(id="vlite-theme-store"),
                            html.Div(id="vlite-theme-dummy", style={"display": "none"}),
                        ],
                    ),
                ],
            )
        ],
    )


layout = vlite_layout

# ── Clientside: AG Grid dark/light mode ────────────────────────────────────────

clientside_callback(
    """
    (theme) => {
       document.documentElement.setAttribute('data-ag-theme-mode', theme === 'dark' ? 'dark' : 'light');
       return window.dash_clientside.no_update;
    }
    """,
    Output("vlite-theme-dummy", "children"),
    Input("theme-store", "data"),
)

# ── Theme passthrough ──────────────────────────────────────────────────────────

@callback(
    Output("vlite-theme-store", "data"),
    Input("theme-store", "data"),
    prevent_initial_call=False,
)
def sync_theme(theme):
    return theme


# ── Usage info toggle ──────────────────────────────────────────────────────────

@callback(
    Output("vlite-usage-open", "data"),
    Input("vlite-usage-toggle", "n_clicks"),
    State("vlite-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage(n_clicks, is_open):
    return not bool(is_open)


@callback(
    Output("vlite-usage-collapse", "opened"),
    Input("vlite-usage-open", "data"),
)
def sync_usage_collapse(is_open):
    return bool(is_open)


# ── Data loading ───────────────────────────────────────────────────────────────

@callback(
    Output("vlite-metadata-store", "data"),
    Input("vlite-order-id-filter", "id"),
)
def load_vlite_metadata(_):
    """Load vlite metadata once on page mount (vlite_meta view: order/sample info + event_id)."""
    return get_metadata("sherlock", "vlite")


@callback(
    Output("vlite-order-id-filter", "options"),
    Input("vlite-metadata-store", "data"),
)
def populate_order_options(metadata):
    if not metadata:
        return []
    df = pd.DataFrame(metadata)
    order_ids = sorted(df["order_id"].dropna().unique(), reverse=True)
    return [{"label": str(oid), "value": oid} for oid in order_ids]


@callback(
    Output("vlite-data-store", "data"),
    Output("vlite-model-store", "data"),
    Output("vlite-model-status", "children"),
    Input("vlite-order-id-filter", "value"),
)
def update_data_on_order_change(order_id):
    """Fetch polcurve data for the selected order; reset model store and status."""
    if not order_id:
        return [], None, ""
    df = get_tabular("sherlock", "vlite", filters={"order_id": order_id})
    if df.empty:
        return [], None, "No polcurve data found for this order."
    return df.to_dict("records"), None, ""


@callback(
    Output("vlite-event-id-filter", "options"),
    Output("vlite-event-id-filter", "value"),
    Input("vlite-data-store", "data"),
)
def update_event_options(data):
    if not data:
        return [], []
    df = pd.DataFrame(data)
    if "event_id" not in df.columns:
        return [], []
    events = sorted(df["event_id"].dropna().unique())
    options = [{"label": str(e), "value": e} for e in events]
    return options, list(events)


@callback(
    Output("vlite-metadata-table", "columnDefs"),
    Output("vlite-metadata-table", "rowData"),
    Input("vlite-metadata-store", "data"),
    Input("vlite-order-id-filter", "value"),
)
def update_metadata_table(metadata, order_id):
    """Show order-level metadata below the polcurve plot (event_id excluded, deduplicated)."""
    if not metadata or not order_id:
        return [], []
    df = pd.DataFrame(metadata)
    df = df[df["order_id"] == order_id]
    cols = [c for c in METADATA_DISPLAY_COLUMNS if c in df.columns]
    df = df[cols].drop_duplicates()
    return [_metadata_column_def(c) for c in cols], df.to_dict("records")


# ── Model run ──────────────────────────────────────────────────────────────────

@callback(
    Output("vlite-model-store", "data", allow_duplicate=True),
    Output("vlite-model-status", "children", allow_duplicate=True),
    Input("vlite-run-model-btn", "n_clicks"),
    State("vlite-data-store", "data"),
    State("vlite-event-id-filter", "value"),
    State("vlite-metadata-store", "data"),
    prevent_initial_call=True,
)
def run_vlite_model(n_clicks, data, selected_events, metadata):
    """Run one V-lite fit across all selected events and split outputs per event for plotting."""
    if not data:
        return no_update, "No polcurve data loaded. Please select an Order ID first."
    if not selected_events:
        return no_update, "No events selected. Please select at least one event."

    df_all = _add_event_short_id(pd.DataFrame(data))
    df_meta = pd.DataFrame(metadata) if metadata else None
    df_fit = df_all[df_all["event_id"].isin(selected_events)].copy().reset_index(drop=True)
    if df_fit.empty:
        return no_update, "No rows found for selected event(s)."

    df_meta_event = None
    if df_meta is not None and "order_id" in df_meta.columns and "order_id" in df_fit.columns:
        order_id = df_fit["order_id"].iloc[0]
        df_meta_event = df_meta[df_meta["order_id"] == order_id].head(1).reset_index(drop=True)

    try:
        inp_serial, out_serial = vlite_run_model(df_fit, df_meta_event)
    except Exception as exc:
        return None, f"Model fit failed: {exc}"

    n_rows = len(df_fit)
    model_store: dict = {}

    def _slice_payload(payload: dict, idxs: list[int]) -> dict:
        sliced: dict = {}
        for key, value in payload.items():
            if isinstance(value, list) and len(value) == n_rows:
                sliced[key] = [value[i] for i in idxs]
            else:
                sliced[key] = value
        return sliced

    for short_id, group in df_fit.groupby("event_short_id", sort=False):
        idxs = group.index.tolist()
        inp_event = _slice_payload(inp_serial, idxs)
        out_event = _slice_payload(out_serial, idxs)
        inp_event["event"] = short_id
        model_store[str(short_id)] = {"inp": inp_event, "out": out_event}

    selected_set = {str(e) for e in selected_events}
    present_set = {str(e) for e in df_fit["event_id"].dropna().unique().tolist()}
    missing_count = len(selected_set - present_set)
    msg = f"Global model fit complete across {len(model_store)} event(s), {n_rows} points, single shared parameter set."
    if missing_count:
        msg += f" Missing selected events: {missing_count}."
    warnings = inp_serial.get("warnings")
    if warnings:
        msg += f" Warning: {warnings}."
    return model_store, msg


# ── Polcurve + model fit plot ──────────────────────────────────────────────────

@callback(
    Output("vlite-polcurve-plot", "figure"),
    Input("vlite-data-store", "data"),
    Input("vlite-event-id-filter", "value"),
    Input("vlite-model-store", "data"),
    Input("vlite-theme-store", "data"),
)
def update_polcurve_plot(data, selected_events, model_store, theme):
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    fig = go.Figure()
    fig.update_layout(
        template=template,
        xaxis_title="Current Density [A/cm²]",
        yaxis_title="Cell Voltage [V]",
        legend=dict(yanchor="top", y=1, xanchor="left", x=1.02),
        margin=dict(l=40, r=20, t=40, b=40),
    )
    if not data:
        return fig

    df = _add_event_short_id(pd.DataFrame(data))
    events_to_show = selected_events if selected_events else df["event_id"].dropna().unique().tolist()

    model_fit_shown = False
    for i, event_id in enumerate(events_to_show):
        df_ev = df[df["event_id"] == event_id]
        if df_ev.empty:
            continue
        color = _TRACE_COLORS[i % len(_TRACE_COLORS)]
        short_id = (
            df_ev["event_short_id"].iloc[0]
            if "event_short_id" in df_ev.columns
            else str(event_id)
        )
        # Measured data: line plot only
        fig.add_trace(go.Scatter(
            x=df_ev["jStck"].tolist(),
            y=df_ev["uCell"].tolist(),
            mode="lines",
            line=dict(color=color, width=2),
            name=short_id,
        ))
        # Model fit: crosses, single grouped legend entry for all fits
        if model_store and short_id in model_store:
            inp = model_store[short_id]["inp"]
            out = model_store[short_id]["out"]
            modelj_cm2 = [j / 1e4 for j in inp["modelj"]]
            cross_color = "#e8e8e8" if theme == "dark" else "#111111"
            fig.add_trace(go.Scatter(
                x=modelj_cm2,
                y=out["V"],
                mode="markers",
                marker=dict(color=cross_color, size=8, symbol="x"),
                name="Model Fit",
                showlegend=not model_fit_shown,
            ))
            model_fit_shown = True

    return fig


# ── Stackup event dropdown ─────────────────────────────────────────────────────

@callback(
    Output("vlite-stackup-event-dropdown", "options"),
    Output("vlite-stackup-event-dropdown", "value"),
    Input("vlite-model-store", "data"),
    State("vlite-stackup-event-dropdown", "value"),
)
def update_stackup_dropdown(model_store, current_val):
    if not model_store:
        return [], None
    options = [{"label": k, "value": k} for k in model_store]
    value = (
        current_val if current_val and current_val in model_store
        else next(iter(model_store))
    )
    return options, value


# ── Loss stackup + DTW plots ───────────────────────────────────────────────────

@callback(
    Output("vlite-stackup-plot", "figure"),
    Output("vlite-dtw-plot", "figure"),
    Input("vlite-stackup-event-dropdown", "value"),
    Input("vlite-data-store", "data"),
    Input("vlite-model-store", "data"),
    Input("vlite-theme-store", "data"),
)
def update_stackup_dtw_plots(selected_event, data, model_store, theme):
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    margin = dict(l=40, r=20, t=40, b=40)
    blank = go.Figure(layout=go.Layout(template=template, margin=margin))

    if not selected_event or not model_store or selected_event not in model_store:
        return blank, blank

    inp = model_store[selected_event]["inp"]
    out = model_store[selected_event]["out"]
    modelj_cm2 = [j / 1e4 for j in inp["modelj"]]
    axis_line_color = "white" if theme == "dark" else "black"

    # ── Loss stackup ─────────────────────────────────────────────────────────
    stackup_fig = go.Figure()
    for key, label, color in [
        ("Erev", "V-lite: OCV", "#1f77b4"),
        ("etaICR", "V-lite: Ohmic ICR", "#ff7f0e"),
        ("etamem", "V-lite: Ohmic Membrane", "#2ca02c"),
        ("etaact", "V-lite: Kinetic", "#d62728"),
    ]:
        if key in out:
            stackup_fig.add_trace(
                go.Scatter(
                    x=modelj_cm2,
                    y=out[key],
                    mode="lines",
                    line=dict(color=color, width=1),
                    stackgroup="one",
                    name=label,
                    legendgroup="stack",
                )
            )

    if "V" in out:
        stackup_fig.add_trace(
            go.Scatter(
                x=modelj_cm2,
                y=out["V"],
                mode="lines",
                name="Model V",
                line=dict(color=axis_line_color, width=2, dash="dot"),
            )
        )

    if data:
        df = _add_event_short_id(pd.DataFrame(data))
        if "event_short_id" in df.columns:
            df_ev = df[df["event_short_id"] == selected_event].copy()
            if not df_ev.empty:
                df_ev = df_ev.sort_values("jStck")
                measured_fill = "#f8f9fa" if theme == "dark" else "#111111"
                stackup_fig.add_trace(
                    go.Scatter(
                        x=df_ev["jStck"].tolist(),
                        y=df_ev["uCell"].tolist(),
                        mode="markers",
                        name="Measured V",
                        showlegend=True,
                        marker=dict(
                            color=measured_fill,
                            size=11,
                            symbol="circle",
                        ),
                    )
                )

    stackup_fig.update_layout(
        template=template,
        xaxis_title="Current Density [A/cm²]",
        yaxis_title="Voltage [V]",
        title=selected_event,
        margin=margin,
        legend=dict(yanchor="top", y=1, xanchor="left", x=1.02),
    )

    # ── DTW plot ─────────────────────────────────────────────────────────────
    dtw_fig = go.Figure()

    if "DTW" in out:
        dtw_fig.add_trace(go.Scatter(
            x=modelj_cm2,
            y=out["DTW"],
            mode="lines+markers",
            name="Model ΔTW",
            line=dict(color="#1f77b4", width=2),
            marker=dict(size=4),
        ))

    if "testDTW" in inp:
        dtw_fig.add_trace(go.Scatter(
            x=modelj_cm2,
            y=inp["testDTW"],
            mode="lines+markers",
            name="Measured ΔTW",
            line=dict(color="#d62728", width=2, dash="dash"),
            marker=dict(size=4),
        ))

    dtw_fig.update_layout(
        template=template,
        xaxis_title="Current Density [A/cm²]",
        yaxis_title="Temperature Rise [K]",
        title=selected_event,
        margin=margin,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return stackup_fig, dtw_fig


# ── Parameter table ────────────────────────────────────────────────────────────

@callback(
    Output("vlite-parameter-table", "children"),
    Input("vlite-model-store", "data"),
)
def update_parameter_table(model_store):
    if not model_store:
        return dmc.Text(
            "Run the model to see fitted parameters.", c="dimmed", size="sm"
        )

    first_event_id = next(iter(model_store))
    global_out = model_store[first_event_id]["out"]
    fitfix = FitFix()

    header_cells = [
        html.Th("", style={"textAlign": "left", "paddingRight": "16px", "whiteSpace": "nowrap"})
    ] + [
        html.Th(
            PARAM_DISPLAY_NAMES.get(key, key),
            style={"textAlign": "right", "paddingLeft": "12px", "whiteSpace": "nowrap"},
        )
        for key in PARAM_KEYS
    ]

    global_row = [
        html.Td(
            "Global Fit",
            style={"fontWeight": "600", "paddingRight": "16px", "whiteSpace": "nowrap"},
        )
    ] + [
        html.Td(
            _fmt_param(global_out.get(key, "—")),
            style={"textAlign": "right", "paddingLeft": "12px", "fontFamily": "monospace"},
        )
        for key in PARAM_KEYS
    ]

    def _fit_cell(key: str) -> html.Td:
        if key == "LSQerravg":
            return html.Td("—", style={"textAlign": "right", "paddingLeft": "12px", "fontFamily": "monospace", "color": "var(--mantine-color-dimmed)"})
        val = getattr(fitfix, key, 0)
        is_fitted = val == 1
        return html.Td(
            str(val),
            style={
                "textAlign": "right",
                "paddingLeft": "12px",
                "fontFamily": "monospace",
                "fontWeight": "700" if is_fitted else "normal",
                "color": "var(--mantine-color-green-6)" if is_fitted else "var(--mantine-color-dimmed)",
            },
        )

    fit_row = [
        html.Td(
            "Fit",
            style={"fontWeight": "600", "paddingRight": "16px", "whiteSpace": "nowrap"},
        )
    ] + [_fit_cell(key) for key in PARAM_KEYS]

    table = html.Table(
        [
            html.Thead(html.Tr(header_cells)),
            html.Tbody([
                html.Tr(fit_row),
                html.Tr(global_row),
            ]),
        ],
        style={
            "width": "100%",
            "borderCollapse": "collapse",
            "fontSize": "13px",
            "tableLayout": "auto",
            "minWidth": "980px",
        },
    )
    return html.Div(table, style={"overflowX": "auto"})


# ── Download ───────────────────────────────────────────────────────────────────

@callback(
    Output("vlite-download-btn", "disabled"),
    Input("vlite-model-store", "data"),
)
def toggle_download_button(model_store):
    return not bool(model_store)


# Per-row model output columns to attach to the download
_MODEL_OUTPUT_COLS = ["V", "Erev", "etaICR", "etamem", "etaact", "DTW"]
_MODEL_OUTPUT_LABELS = {
    "V": "uCell_vlite",
    "Erev": "Erev",
    "etaICR": "etaICR",
    "etamem": "etamem",
    "etaact": "etaact",
    "DTW": "DTW_model",
}


@callback(
    Output("vlite-download-csv", "data"),
    Input("vlite-download-btn", "n_clicks"),
    State("vlite-data-store", "data"),
    State("vlite-model-store", "data"),
    State("vlite-event-id-filter", "value"),
    State("vlite-order-id-filter", "value"),
    prevent_initial_call=True,
)
def download_vlite_data(n_clicks, data, model_store, selected_events, order_id):
    if not data or not model_store:
        return no_update
    df = _add_event_short_id(pd.DataFrame(data))
    if selected_events:
        df = df[df["event_id"].isin(selected_events)]
    df = df.copy().reset_index(drop=True)

    # Attach per-row model outputs and scalar fit parameters
    for col_label in _MODEL_OUTPUT_LABELS.values():
        df[col_label] = float("nan")

    first_out = next(iter(model_store.values()))["out"]
    scalar_params = {k: v for k, v in first_out.items() if not isinstance(v, list)}

    for short_id, entry in model_store.items():
        mask = df["event_short_id"] == short_id
        out = entry["out"]
        for src_key, dst_col in _MODEL_OUTPUT_LABELS.items():
            if src_key in out and isinstance(out[src_key], list):
                vals = out[src_key]
                idxs = df.index[mask].tolist()
                if len(vals) == len(idxs):
                    for idx, val in zip(idxs, vals):
                        df.at[idx, dst_col] = val

    for param_key, param_val in scalar_params.items():
        df[param_key] = param_val

    filename = f"vlite_results_{order_id}.csv" if order_id else "vlite_results.csv"
    return send_data_frame(df.to_csv, filename, index=False)
