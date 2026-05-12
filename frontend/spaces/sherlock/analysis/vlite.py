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
from services.vlite_service import run_model as vlite_run_model

register_page(
    __name__, path="/sherlock/data-analysis/vlite", title="HOLMES - Sherlock - V-Lite"
)

# ── Constants ──────────────────────────────────────────────────────────────────

USAGE_BLOCKQUOTE_TEXT = [
    "Select an Order ID to load polarisation curve data for that order.",
    "Choose one or more events from the Event ID(s) dropdown, then click 'Run Model' to fit the V-lite model.",
    "After the model runs, select an event in the Results section to see the loss stackup and DTW plots.",
    "Download the polcurve data as CSV using the Download CSV button.",
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

METADATA_DISPLAY_COLUMNS = [
    "order_id", "name", "testrig_id", "number_of_cells",
    "active_area_per_cell", "ccm_thickness", "ccm_name",
]

METADATA_COLUMN_WIDTHS = {
    "order_id": 120, "name": 150, "testrig_id": 110,
    "number_of_cells": 100, "active_area_per_cell": 160,
    "ccm_thickness": 120, "ccm_name": 140,
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


def _metadata_column_def(col: str) -> dict:
    return {
        "headerName": METADATA_COLUMN_LABELS.get(col, col),
        "field": col,
        "width": METADATA_COLUMN_WIDTHS.get(col, 120),
    }


# ── Layout ─────────────────────────────────────────────────────────────────────

def vlite_layout():
    return dmc.Container(
        size="xl",
        py="md",
        children=[
            dmc.Stack(
                gap="md",
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

                    # ── Filter section ──────────────────────────────────────────
                    dmc.Paper(
                        withBorder=True,
                        p="md",
                        radius="md",
                        children=[
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
                                                style={"marginRight": "8px", "fontSize": "1.1em"},
                                            ),
                                            "Download CSV",
                                        ],
                                        id="vlite-download-btn",
                                        n_clicks=0,
                                        variant="outline",
                                        disabled=True,
                                        style={"flex": "0 0 auto", "whiteSpace": "nowrap"},
                                    ),
                                    dcc.Download(id="vlite-download-csv"),
                                ],
                            ),
                            dmc.Space(h="sm"),
                            dmc.Text(id="vlite-model-status", c="dimmed", size="sm"),
                        ],
                    ),

                    # ── Content cards ───────────────────────────────────────────
                    dmc.SimpleGrid(
                        cols=1,
                        spacing="md",
                        verticalSpacing="md",
                        children=[
                            # Card 1: Polcurve + model fit plot + order metadata
                            dmc.Paper(
                                withBorder=True,
                                p="md",
                                radius="md",
                                children=[
                                    dmc.Text("Polcurve + Model Fit", fw=600, mb="xs"),
                                    dcc.Graph(
                                        id="vlite-polcurve-plot",
                                        style={"height": 420},
                                    ),
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
                                        },
                                        dashGridOptions={
                                            "pagination": False,
                                            "domLayout": "normal",
                                            "rowHeight": 32,
                                            "headerHeight": 32,
                                        },
                                        style={"height": "64px", "width": "100%"},
                                    ),
                                ],
                            ),

                            # Card 2: Model result plots (event selector + stackup + DTW)
                            dmc.Paper(
                                withBorder=True,
                                p="md",
                                radius="md",
                                children=[
                                    dmc.Text("Polcurve Model Results Plots", fw=600, mb="xs"),
                                    dcc.Dropdown(
                                        id="vlite-stackup-event-dropdown",
                                        multi=False,
                                        placeholder="Select event for detailed plots",
                                        style={"width": "100%"},
                                    ),
                                    dmc.Space(h="sm"),
                                    dmc.SimpleGrid(
                                        cols=2,
                                        spacing="md",
                                        children=[
                                            dmc.Paper(
                                                withBorder=True,
                                                p="md",
                                                radius="md",
                                                children=[
                                                    dmc.Text("Loss Stackup", fw=600, mb="xs"),
                                                    dcc.Graph(
                                                        id="vlite-stackup-plot",
                                                        style={"height": 395},
                                                    ),
                                                ],
                                            ),
                                            dmc.Paper(
                                                withBorder=True,
                                                p="md",
                                                radius="md",
                                                children=[
                                                    dmc.Text("DTW", fw=600, mb="xs"),
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

                            # Card 3: Model parameters table
                            dmc.Paper(
                                withBorder=True,
                                p="md",
                                radius="md",
                                style={"minHeight": "120px"},
                                children=[
                                    dmc.Text("Model Parameters", fw=600, mb="xs"),
                                    html.Div(id="vlite-parameter-table"),
                                ],
                            ),
                        ],
                    ),

                    # ── Stores ──────────────────────────────────────────────────
                    dcc.Store(id="vlite-metadata-store"),
                    dcc.Store(id="vlite-data-store"),
                    dcc.Store(id="vlite-model-store"),
                    dcc.Store(id="vlite-usage-open", data=False),
                    dcc.Store(id="vlite-theme-store"),
                    html.Div(id="vlite-theme-dummy", style={"display": "none"}),
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
    """Run V-lite model for each selected event; store results keyed by event_short_id."""
    if not data:
        return no_update, "No polcurve data loaded. Please select an Order ID first."
    if not selected_events:
        return no_update, "No events selected. Please select at least one event."

    df_all = _add_event_short_id(pd.DataFrame(data))
    df_meta = pd.DataFrame(metadata) if metadata else None

    model_store: dict = {}
    errors: list[str] = []

    for event_id in selected_events:
        df_event = df_all[df_all["event_id"] == event_id].copy()
        if df_event.empty:
            errors.append(f"{event_id}: no rows found")
            continue
        df_meta_event = None
        if df_meta is not None and "order_id" in df_meta.columns:
            order_id = df_event["order_id"].iloc[0]
            df_meta_event = (
                df_meta[df_meta["order_id"] == order_id].head(1).reset_index(drop=True)
            )
        try:
            inp_serial, out_serial = vlite_run_model(df_event, df_meta_event)
            short_id = inp_serial.get("event", str(event_id))
            model_store[short_id] = {"inp": inp_serial, "out": out_serial}
        except Exception as exc:
            errors.append(f"{event_id}: {exc}")

    if not model_store:
        return None, f"Model failed for all events. Errors: {'; '.join(errors)}"

    parts = [f"Model fit complete for {len(model_store)} event(s)."]
    if errors:
        parts.append(f"Failed ({len(errors)}): {'; '.join(errors)}")
    return model_store, " ".join(parts)


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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=40, b=40),
    )
    if not data:
        return fig

    df = _add_event_short_id(pd.DataFrame(data))
    events_to_show = selected_events if selected_events else df["event_id"].dropna().unique().tolist()

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
        fig.add_trace(go.Scatter(
            x=df_ev["jStck"].tolist(),
            y=df_ev["uCell"].tolist(),
            mode="markers",
            marker=dict(color=color, size=5, opacity=0.7),
            name=short_id,
            legendgroup=short_id,
        ))
        if model_store and short_id in model_store:
            inp = model_store[short_id]["inp"]
            out = model_store[short_id]["out"]
            modelj_cm2 = [j / 1e4 for j in inp["modelj"]]
            fig.add_trace(go.Scatter(
                x=modelj_cm2,
                y=out["V"],
                mode="lines",
                line=dict(color=color, width=2),
                name=f"{short_id} (fit)",
                legendgroup=short_id,
            ))

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
        ("Erev",   "Reversible [V]", "#1f77b4"),
        ("etaICR", "η ICR [V]",      "#ff7f0e"),
        ("etamem", "η Mem [V]",      "#2ca02c"),
        ("etaact", "η Act [V]",      "#d62728"),
    ]:
        if key in out:
            stackup_fig.add_trace(go.Bar(
                x=modelj_cm2,
                y=out[key],
                name=label,
                marker_color=color,
            ))

    if "V" in out:
        stackup_fig.add_trace(go.Scatter(
            x=modelj_cm2,
            y=out["V"],
            mode="lines",
            name="Model V",
            line=dict(color=axis_line_color, width=2, dash="dash"),
        ))

    if data:
        df = _add_event_short_id(pd.DataFrame(data))
        if "event_short_id" in df.columns:
            df_ev = df[df["event_short_id"] == selected_event]
            if not df_ev.empty:
                stackup_fig.add_trace(go.Scatter(
                    x=df_ev["jStck"].tolist(),
                    y=df_ev["uCell"].tolist(),
                    mode="markers",
                    name="Measured V",
                    marker=dict(color=axis_line_color, size=6, symbol="x"),
                ))

    stackup_fig.update_layout(
        template=template,
        barmode="stack",
        xaxis_title="Current Density [A/cm²]",
        yaxis_title="Voltage [V]",
        title=selected_event,
        margin=margin,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
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

    event_ids = list(model_store.keys())
    header_cells = [
        html.Th("Parameter", style={"textAlign": "left", "paddingRight": "16px"})
    ] + [
        html.Th(eid, style={"textAlign": "right", "paddingLeft": "12px"})
        for eid in event_ids
    ]

    rows = []
    for key in PARAM_KEYS:
        label = PARAM_DISPLAY_NAMES.get(key, key)
        is_fitted = key in PARAM_FITTED
        cells = [
            html.Td(
                label,
                style={
                    "fontWeight": "600" if is_fitted else "normal",
                    "paddingRight": "16px",
                    "whiteSpace": "nowrap",
                },
            )
        ]
        for eid in event_ids:
            val = model_store[eid]["out"].get(key, "—")
            cells.append(html.Td(
                _fmt_param(val),
                style={"textAlign": "right", "paddingLeft": "12px", "fontFamily": "monospace"},
            ))
        rows.append(html.Tr(cells))

    return html.Table(
        [html.Thead(html.Tr(header_cells)), html.Tbody(rows)],
        style={
            "width": "100%",
            "borderCollapse": "collapse",
            "fontSize": "13px",
            "tableLayout": "auto",
        },
    )


# ── Download ───────────────────────────────────────────────────────────────────

@callback(
    Output("vlite-download-btn", "disabled"),
    Input("vlite-data-store", "data"),
)
def toggle_download_button(data):
    return not bool(data)


@callback(
    Output("vlite-download-csv", "data"),
    Input("vlite-download-btn", "n_clicks"),
    State("vlite-data-store", "data"),
    State("vlite-event-id-filter", "value"),
    prevent_initial_call=True,
)
def download_vlite_data(n_clicks, data, selected_events):
    if not data:
        return no_update
    df = pd.DataFrame(data)
    if selected_events:
        df = df[df["event_id"].isin(selected_events)]
    return send_data_frame(df.to_csv, "vlite_polcurve.csv", index=False)
