"""standard_reports -- Dash tab for standard report visualization.

Provides ``layout()`` which returns the tab's component tree and
``register_callbacks(app, data_manager)`` which wires up all interactivity.

Key features
------------
* Ribbon bar at the top (~10 %) with Series, Report, and Time Slicer controls.
* ``dcc.Graph`` filling ~90 % of the viewport with built-in range slider.
* On-the-fly reporting data loading with automatic unload of the previous series.
* **Server-side data**: DataFrames are kept in server memory â€“ never
  serialised to JSON.  ``dcc.Store`` holds only lightweight string keys.
* **SVG rendering**: Traces are kept as SVG ``Scatter`` (not ``Scattergl``)
  so the built-in range-slider miniature renders correctly.
* **Padded window**: When a time slicer is active the DataFrame is trimmed
  to 2\u00d7 the slicer span, keeping traces lightweight while giving the
  range-slider handles room to drag.
* Three-level dynamic aggregation switching on zoom:
    - coarse  (> 100 h visible)  â†’ 15-min aggregation
    - medium  (10 â€“ 100 h visible) â†’ 1-min aggregation
    - fine    (< 10 h visible)   â†’ raw (1-second) data
* Bidirectional sync between time-slicer inputs and the range slider.
* Manual Y-axis range override inputs.
"""

import json
import os
import uuid

import plotly.io as pio
import dash_bootstrap_components as dbc
from dash import dcc, html, no_update
from dash.dependencies import Input, Output, State

from pathlib import Path

from ..data_provider import CHANNEL_ALIASES
from ..model import SeriesDataManager
from ..visualization import plot_report
from .export_helpers import (
    build_save_modal,
    clean_rangeslider_for_export,
    download_cache,
    EXT_MAP,
    generate_default_graph_filename,
    get_graph_file_type_options,
    spinner_style,
)
from .tab_helpers import (
    ServerDataCache,
    apply_axis_overrides,
    approx_equal,
    build_window_status,
    empty_figure,
    finalise_figure,
    initial_resolution,
    pick_resolution,
    resolution_label,
)

STANDARD_REPORTS_PATH = Path(__file__).resolve().parents[1] / "config" / "standard_reports.json"

# ---------------------------------------------------------------------------
# Server-side data cache (one instance for this tab)
# ---------------------------------------------------------------------------
_cache = ServerDataCache()


def _load_standard_reports():
    """Load standard report definitions from JSON."""
    with open(STANDARD_REPORTS_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)


STANDARD_REPORTS = _load_standard_reports()


def _query_columns_for_report(report, series, data_manager: SeriesDataManager) -> list[str]:
    columns = [*report.get("y1_cols", []), *report.get("y2_cols", [])]
    if columns:
        return columns
    return [
        row.get("std_channel") or row.get("channel_name")
        for row in data_manager.list_channels(series)
        if row.get("std_channel") or row.get("channel_name")
    ]


def _drop_alias_duplicate_columns(df):
    duplicate_columns = []
    for alias, canonical in CHANNEL_ALIASES.items():
        for suffix in ("", "_mean", "_min", "_max"):
            alias_column = f"{alias}{suffix}"
            canonical_column = f"{canonical}{suffix}"
            if alias_column in df.columns and canonical_column in df.columns:
                duplicate_columns.append(alias_column)
    return df.drop(columns=duplicate_columns) if duplicate_columns else df


def _series_default_window_h(series, fallback_hours: float = 24.0) -> tuple[float, float]:
    try:
        start_h = max(0.0, float(series.start_time or 0.0) / 3600.0)
    except (TypeError, ValueError):
        start_h = 0.0
    try:
        end_h = max(start_h, float(series.end_time or 0.0) / 3600.0)
    except (TypeError, ValueError):
        end_h = start_h
    visible_end_h = min(end_h, start_h + fallback_hours) if end_h > start_h else start_h + fallback_hours
    return start_h, visible_end_h


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def layout(data_manager: SeriesDataManager):
    """Return the Dash component tree for the Standard Reports tab."""

    # Show only parent series â€“ aggregation levels are handled by dynamic
    # zoom switching, so aggregated entries would be redundant.
    series_options = [
        {"label": s, "value": s}
        for s in data_manager.series_defs.keys()
    ]

    report_options = [
        {"label": r["name"], "value": i}
        for i, r in enumerate(STANDARD_REPORTS)
    ]

    return html.Div(
        style={
            "flex": "1 1 auto",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "minHeight": "0",
        },
        children=[
            # ---- lightweight stores (strings / small metadata only) ----
            dcc.Store(id="store-current-series", storage_type="memory"),
            dcc.Store(id="store-active-resolution", storage_type="memory"),
            # agg-levels: [{interval, name}] â€” NO DataFrame payload
            dcc.Store(id="store-agg-levels", storage_type="memory"),
            # trigger counter: bumped when server-side data is ready
            dcc.Store(id="store-data-ready", storage_type="memory", data=0),
            dcc.Store(id="store-std-save-mode", storage_type="memory"),  # "graph"
            dcc.Store(id="store-std-pending-data", storage_type="memory"),  # Context for graph save
            dcc.Store(id="store-std-is-saving", storage_type="memory", data=False),

            # ---- download/save modal + download trigger ----
            *build_save_modal("std"),

            # ---- ribbon bar ----
            dbc.Card(
                dbc.CardBody(
                    dbc.Row(
                        [
                            # Series selector
                            dbc.Col([
                                dbc.Label("Series", className="fw-bold small mb-0"),
                                dcc.Dropdown(
                                    id="dd-series",
                                    options=series_options,
                                    value=series_options[0]["value"] if series_options else None,
                                    clearable=False,
                                    style={"fontSize": "0.85rem"},
                                ),
                            ], width=2),

                            # Report selector
                            dbc.Col([
                                dbc.Label("Report", className="fw-bold small mb-0"),
                                dcc.Dropdown(
                                    id="dd-report",
                                    options=report_options,
                                    value=0,
                                    clearable=False,
                                    style={"fontSize": "0.85rem"},
                                ),
                            ], width=2),

                            # Time slicer
                            dbc.Col([
                                dbc.Label("Time slicer [h]", className="fw-bold small mb-0"),
                                dbc.InputGroup([
                                    dbc.Input(id="input-time-min", type="number",
                                              placeholder="min", size="sm"),
                                    dbc.InputGroupText("-", className="px-1"),
                                    dbc.Input(id="input-time-max", type="number",
                                              placeholder="max", size="sm"),
                                ], size="sm"),
                            ], width=2),

                            # Y1 axis override
                            dbc.Col([
                                dbc.Label("Y1 range", className="fw-bold small mb-0"),
                                dbc.InputGroup([
                                    dbc.Input(id="input-y1-min", type="number",
                                              placeholder="min", size="sm"),
                                    dbc.InputGroupText("-", className="px-1"),
                                    dbc.Input(id="input-y1-max", type="number",
                                              placeholder="max", size="sm"),
                                ], size="sm"),
                            ], width=2),

                            # Y2 axis override
                            dbc.Col([
                                dbc.Label("Y2 range", className="fw-bold small mb-0"),
                                dbc.InputGroup([
                                    dbc.Input(id="input-y2-min", type="number",
                                              placeholder="min", size="sm"),
                                    dbc.InputGroupText("-", className="px-1"),
                                    dbc.Input(id="input-y2-max", type="number",
                                              placeholder="max", size="sm"),
                                ], size="sm"),
                            ], width=2),
                            # Resolution override
                            dbc.Col([
                                dbc.Label("Resolution",
                                          className="fw-bold small mb-0"),
                                dcc.Dropdown(
                                    id="dd-resolution",
                                    options=[{"label": "auto",
                                              "value": "auto"}],
                                    value="auto",
                                    clearable=False,
                                    style={"fontSize": "0.85rem",
                                           "minWidth": "80px"},
                                ),
                            ], width=1, style={"minWidth": "90px"}),
                            # Reset + Save Graph (grouped, no-wrap)
                            dbc.Col(
                                html.Div([
                                    dbc.Button(
                                        "Reset",
                                        id="btn-reset-zoom",
                                        color="dark",
                                        size="sm",
                                    ),
                                    dbc.Button(
                                        "Save graph",
                                        id="btn-std-save-graph",
                                        color="dark",
                                        size="sm",
                                    ),
                                ], className="d-flex gap-1 align-items-end mt-3"),
                                width="auto",
                            ),
                        ],
                        align="end",
                        className="g-2",
                    ),
                    className="py-2 px-3 co-reporting-toolbar-body",
                ),
                className="mb-1 shadow-sm co-reporting-toolbar-card",
            ),

            # ---- status badge ----
            html.Div(
                id="status-bar",
                className="text-muted small px-3 py-1",
                children="Select a series and report to begin.",
            ),

            # ---- main graph ----
            html.Div(
                className="co-reporting-graph-frame",
                children=dcc.Graph(
                    id="graph-report",
                    className="co-reporting-graph",
                    style={
                        "height": "max(560px, calc(100vh - 17rem))",
                        "width": "100%",
                    },
                    config={
                        "displayModeBar": True,
                        "scrollZoom": True,
                        "displaylogo": False,
                        "responsive": True,
                    },
                ),
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_callbacks(app, data_manager: SeriesDataManager):
    """Wire up all callbacks for the Standard Reports tab."""

    @app.callback(
        Output("btn-reset-zoom", "disabled"),
        Output("btn-reset-zoom", "color"),
        Output("btn-std-save-graph", "disabled"),
        Output("btn-std-save-graph", "color"),
        Input("store-current-series", "data"),
        Input("graph-report", "figure"),
        Input("input-time-min", "value"),
        Input("input-time-max", "value"),
        Input("input-y1-min", "value"),
        Input("input-y1-max", "value"),
        Input("input-y2-min", "value"),
        Input("input-y2-max", "value"),
        Input("dd-resolution", "value"),
        prevent_initial_call=False,
    )
    def set_standard_button_states(series_name, figure,
                                   tmin, tmax, y1min, y1max, y2min, y2max,
                                   resolution):
        has_series = bool(series_name)
        has_fig = bool(figure and figure.get("data"))
        reset_useful = any(v is not None for v in [tmin, tmax, y1min, y1max, y2min, y2max]) or (resolution not in (None, "auto"))

        reset_disabled = not reset_useful
        reset_color = "secondary" if reset_disabled else "dark"

        save_disabled = not (has_series and has_fig)
        save_color = "secondary" if save_disabled else "dark"

        return reset_disabled, reset_color, save_disabled, save_color

    @app.callback(
        Output("dd-series", "options"),
        Output("dd-series", "value"),
        Input("store-series-refresh", "data"),
        State("dd-series", "value"),
        prevent_initial_call=False,
    )
    def refresh_series_dropdown(_refresh_tick, current_value):
        series_options = [
            {"label": s, "value": s}
            for s in data_manager.series_defs.keys()
        ]
        valid_values = {o["value"] for o in series_options}
        if current_value in valid_values:
            return series_options, current_value
        new_value = series_options[0]["value"] if series_options else None
        return series_options, new_value

    # ------------------------------------------------------------------
    # 1) Series changed â†’ load data server-side, unload previous series
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-current-series", "data"),
        Output("store-agg-levels", "data"),
        Output("store-data-ready", "data"),
        Output("dd-resolution", "options"),
        Output("dd-resolution", "value"),
        Output("status-bar", "children"),
        Input("dd-series", "value"),
        State("store-current-series", "data"),
        State("store-data-ready", "data"),
    )
    def on_series_changed(series_name, prev_series, prev_trigger):
        if not series_name:
            return (no_update, no_update, no_update,
                    no_update, no_update,
                    "No series selected.")

        if prev_series and prev_series != series_name:
            parent_prev, _ = SeriesDataManager._parse_agg_name(prev_series)
            _cache.drop_series(parent_prev)
            for key in list(data_manager.loaded_series.keys()):
                p, _ = SeriesDataManager._parse_agg_name(key)
                if p == parent_prev:
                    data_manager.unload_series(key)

        parent, _ = SeriesDataManager._parse_agg_name(series_name)
        series_def = data_manager.series_defs.get(parent, {})
        agg_intervals = sorted(series_def.get("aggregations", []), reverse=True)
        agg_levels_meta = [{"interval": interval, "name": f"{parent}_agg{interval}min"} for interval in agg_intervals]
        res_options = [
            {"label": "auto", "value": "auto"},
            {"label": "raw", "value": "raw"},
            *[
                {"label": f"{item['interval']} min", "value": f"agg{item['interval']}"}
                for item in sorted(agg_levels_meta, key=lambda meta: meta["interval"])
            ],
        ]

        trigger = (prev_trigger or 0) + 1
        status = f"Selected '{series_name}' - Windowed query mode enabled"
        return (series_name, agg_levels_meta, trigger,
                res_options, "auto", status)

    # ------------------------------------------------------------------
    # 2) Data ready / report / slicer / Y-axis changed â†’ render figure
    # ------------------------------------------------------------------
    @app.callback(
        Output("graph-report", "figure"),
        Output("store-active-resolution", "data"),
        Output("status-bar", "children", allow_duplicate=True),
        Input("store-data-ready", "data"),
        Input("dd-report", "value"),
        Input("input-time-min", "value"),
        Input("input-time-max", "value"),
        Input("input-y1-min", "value"),
        Input("input-y1-max", "value"),
        Input("input-y2-min", "value"),
        Input("input-y2-max", "value"),
        Input("dd-resolution", "value"),
        State("store-current-series", "data"),
        State("store-agg-levels", "data"),
        prevent_initial_call=False,
    )
    def render_report(
        data_trigger, report_idx,
        time_min, time_max,
        y1_min, y1_max, y2_min, y2_max,
        res_override,
        current_series, agg_levels,
    ):
        if not current_series or report_idx is None:
            return empty_figure("Select a series and report."), no_update, "Select a series and report."

        parent, _ = SeriesDataManager._parse_agg_name(current_series)
        report = STANDARD_REPORTS[report_idx]
        series = data_manager._series_from_key(parent)
        if series is None:
            return empty_figure("Series metadata unavailable."), no_update, "Series metadata unavailable."

        report_columns = _query_columns_for_report(report, series, data_manager)
        default_start_h, default_end_h = _series_default_window_h(series)
        visible_start_h = float(time_min) if time_min is not None else default_start_h
        visible_end_h = float(time_max) if time_max is not None else default_end_h
        if visible_end_h <= visible_start_h:
            visible_end_h = visible_start_h + 24.0

        res_override = res_override or "auto"
        query_resolution = res_override
        df = data_manager.query_timeseries_window(
            series,
            report_columns,
            visible_start_s=visible_start_h * 3600.0,
            visible_end_s=visible_end_h * 3600.0,
            prefetch_margin_s=max((visible_end_h - visible_start_h) * 1800.0, 1800.0),
            resolution=query_resolution,
            mode="standard_report",
            report_id=report.get("internal_key") or report.get("name"),
            include_band=True,
        )
        served_resolution = str(df.attrs.get("meta", {}).get("served_resolution") or query_resolution)
        cache_resolution = "raw" if served_resolution == "raw" else served_resolution.replace("_", "")
        _cache.put(parent, cache_resolution, df)

        if df is None or df.empty:
            return empty_figure("No data available."), served_resolution, "No data available."

        fig = _build_figure(df, report, data_manager)
        apply_axis_overrides(fig, y1_min, y1_max, y2_min, y2_max)
        fig.update_xaxes(range=[visible_start_h, visible_end_h])

        meta = df.attrs.get("meta", {})
        status = build_window_status(
            current_series,
            served_resolution,
            len(df),
            query_start_s=meta.get("query_start_s"),
            query_end_s=meta.get("query_end_s"),
        )
        return fig, cache_resolution, status

    # ------------------------------------------------------------------
    # 3) Zoom/pan â†’ switch resolution if needed + sync slicer inputs
    # ------------------------------------------------------------------
    NO_UPD_5 = (no_update,) * 5          # convenience for early returns

    @app.callback(
        Output("graph-report", "figure", allow_duplicate=True),
        Output("store-active-resolution", "data", allow_duplicate=True),
        Output("status-bar", "children", allow_duplicate=True),
        Output("input-time-min", "value", allow_duplicate=True),
        Output("input-time-max", "value", allow_duplicate=True),
        Input("graph-report", "relayoutData"),
        State("store-active-resolution", "data"),
        State("store-agg-levels", "data"),
        State("store-current-series", "data"),
        State("dd-report", "value"),
        State("input-time-min", "value"),
        State("input-time-max", "value"),
        State("input-y1-min", "value"),
        State("input-y1-max", "value"),
        State("input-y2-min", "value"),
        State("input-y2-max", "value"),
        State("dd-resolution", "value"),
        prevent_initial_call=True,
    )
    def on_zoom(
        relayout_data, current_resolution,
        agg_levels, current_series, report_idx,
        time_min, time_max,
        y1_min, y1_max, y2_min, y2_max,
        res_override,
    ):
        if not relayout_data or not current_series:
            return NO_UPD_5

        parent, _ = SeriesDataManager._parse_agg_name(current_series)

        # Extract visible x-range (in hours, as displayed by plot_report).
        # Plotly may emit bracket-indexed keys or an array â€“ handle both.
        x0 = relayout_data.get("xaxis.range[0]")
        x1 = relayout_data.get("xaxis.range[1]")
        if x0 is None and x1 is None:
            xrange = relayout_data.get("xaxis.range")
            if isinstance(xrange, (list, tuple)) and len(xrange) == 2:
                x0, x1 = xrange

        # --- Determine new slicer values and desired resolution --------
        new_tmin = no_update
        new_tmax = no_update

        if relayout_data.get("xaxis.autorange"):
            # Double-click reset â†’ clear slicer, show full data
            desired = initial_resolution(agg_levels)
            new_tmin = None
            new_tmax = None
        elif x0 is not None and x1 is not None:
            x0_f, x1_f = float(x0), float(x1)
            span_seconds = (x1_f - x0_f) * 3600
            desired = pick_resolution(span_seconds, agg_levels)

            # Write back rounded values to slicer inputs
            new_tmin = round(x0_f, 2)
            new_tmax = round(x1_f, 2)
        else:
            # Non-zoom event (figure replacement, resize, etc.) â†’ ignore
            return NO_UPD_5
        # When user has forced a resolution, skip automatic switching
        res_override = res_override or "auto"
        if res_override != "auto":
            desired = res_override
        # If resolution hasn't changed AND slicer values haven't
        # materially changed, skip the rebuild to avoid loops.
        slicer_unchanged = (
            approx_equal(new_tmin, time_min)
            and approx_equal(new_tmax, time_max)
        )
        if desired == current_resolution and slicer_unchanged:
            return NO_UPD_5

        # Slicer values changed but resolution is the same â†’
        # just sync the slicer inputs; no figure rebuild needed.
        if desired == current_resolution:
            return no_update, no_update, no_update, new_tmin, new_tmax

        # Resolution changed — fetch the needed window through the backend
        if report_idx is None:
            return NO_UPD_5

        report = STANDARD_REPORTS[report_idx]
        series = data_manager._series_from_key(parent)
        if series is None:
            return NO_UPD_5

        eff_tmin = new_tmin if new_tmin is not no_update else time_min
        eff_tmax = new_tmax if new_tmax is not no_update else time_max
        default_start_h, default_end_h = _series_default_window_h(series)
        visible_start_h = float(eff_tmin) if eff_tmin is not None else default_start_h
        visible_end_h = float(eff_tmax) if eff_tmax is not None else default_end_h
        if visible_end_h <= visible_start_h:
            visible_end_h = visible_start_h + 24.0

        report_columns = _query_columns_for_report(report, series, data_manager)
        df = data_manager.query_timeseries_window(
            series,
            report_columns,
            visible_start_s=visible_start_h * 3600.0,
            visible_end_s=visible_end_h * 3600.0,
            prefetch_margin_s=max((visible_end_h - visible_start_h) * 1800.0, 1800.0),
            resolution=desired,
            mode="standard_report",
            report_id=report.get("internal_key") or report.get("name"),
            include_band=True,
        )
        served_resolution = str(df.attrs.get("meta", {}).get("served_resolution") or desired)
        cache_resolution = "raw" if served_resolution == "raw" else served_resolution.replace("_", "")
        _cache.put(parent, cache_resolution, df)

        if df is None or df.empty:
            return (
                empty_figure("No data in range."),
                served_resolution,
                f"Resolution: {served_resolution} (no data in range)",
                new_tmin, new_tmax,
            )

        fig = _build_figure(df, report, data_manager)
        apply_axis_overrides(fig, y1_min, y1_max, y2_min, y2_max)
        if x0 is not None and x1 is not None:
            fig.update_xaxes(range=[float(x0), float(x1)])

        meta = df.attrs.get("meta", {})
        status = build_window_status(
            current_series,
            served_resolution,
            len(df),
            query_start_s=meta.get("query_start_s"),
            query_end_s=meta.get("query_end_s"),
        )
        return fig, cache_resolution, status, new_tmin, new_tmax

    # ------------------------------------------------------------------
    # 4) Reset zoom â†’ clear all range inputs, replot at coarsest level
    # ------------------------------------------------------------------
    @app.callback(
        Output("input-time-min", "value", allow_duplicate=True),
        Output("input-time-max", "value", allow_duplicate=True),
        Output("input-y1-min", "value", allow_duplicate=True),
        Output("input-y1-max", "value", allow_duplicate=True),
        Output("input-y2-min", "value", allow_duplicate=True),
        Output("input-y2-max", "value", allow_duplicate=True),
        Output("dd-resolution", "value", allow_duplicate=True),
        Input("btn-reset-zoom", "n_clicks"),
        prevent_initial_call=True,
    )
    def on_reset_zoom(n_clicks):
        """Clear all slicer / Y-axis inputs \u2192 triggers render_report
        which will see no slicer \u2192 full data at coarsest resolution."""
        return None, None, None, None, None, None, "auto"

    # ------------------------------------------------------------------
    # 5) Save Graph â†’ open modal to choose filename/type
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-std-save", "is_open"),
        Output("store-std-save-mode", "data"),
        Output("store-std-pending-data", "data"),
        Output("input-std-save-filename", "value"),
        Output("dd-std-save-filetype", "options"),
        Output("dd-std-save-filetype", "value"),
        Output("status-bar", "children", allow_duplicate=True),
        Output("store-std-is-saving", "data", allow_duplicate=True),
        Input("btn-std-save-graph", "n_clicks"),
        State("graph-report", "figure"),
        State("store-current-series", "data"),
        State("store-active-resolution", "data"),
        State("store-agg-levels", "data"),
        State("dd-report", "value"),
        prevent_initial_call=True,
    )
    def on_save_graph_open_modal(n, figure_dict, series_name, current_resolution,
                                 agg_levels, report_idx):
        if not series_name or not figure_dict:
            return no_update, no_update, no_update, no_update, no_update, no_update, "No chart to save - load a series first.", False

        graph_data_id = str(uuid.uuid4())

        try:
            clean_rangeslider_for_export(figure_dict)
            html_bytes = pio.to_html(figure_dict, include_plotlyjs='cdn')
            download_cache[graph_data_id] = {
                "html": html_bytes,
                "series_name": series_name,
            }
        except Exception as fig_err:
            return no_update, no_update, no_update, no_update, no_update, no_update, f"Failed to prepare graph for export: {str(fig_err)[:100]}", False

        default_filename = generate_default_graph_filename(series_name)
        file_type_opts = get_graph_file_type_options()

        pending_data = {
            "mode": "graph",
            "graph_data_id": graph_data_id,
            "figure_dict": figure_dict,
            "series_name": series_name,
            "current_resolution": current_resolution,
            "agg_levels": agg_levels,
            "report_idx": report_idx,
        }

        return True, "graph", pending_data, default_filename, file_type_opts, "html", "", False

    # ------------------------------------------------------------------
    # 6) Modal cancel button
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-std-save", "is_open", allow_duplicate=True),
        Input("btn-std-modal-cancel", "n_clicks"),
        prevent_initial_call=True,
    )
    def on_modal_cancel(n):
        return False

    # ------------------------------------------------------------------
    # 7) Modal save button â†’ generate file and trigger download
    # ------------------------------------------------------------------
    @app.callback(
        Output("download-std-file", "data"),
        Output("modal-std-save", "is_open", allow_duplicate=True),
        Output("status-bar", "children", allow_duplicate=True),
        Input("btn-std-modal-save", "n_clicks"),
        State("input-std-save-filename", "value"),
        State("dd-std-save-filetype", "value"),
        State("store-std-pending-data", "data"),
        prevent_initial_call=True,
    )
    def on_modal_save(n, filename, filetype, pending_data):
        if not filename or not filetype or not pending_data:
            return no_update, False, "Invalid save parameters."

        try:
            filename_clean = filename.strip()
            if not filename_clean:
                return no_update, False, "Filename cannot be empty."

            ext = EXT_MAP.get(filetype, ".txt")
            full_filename = f"{filename_clean}{ext}"

            figure_dict = pending_data["figure_dict"]
            series_name = pending_data["series_name"]
            current_resolution = pending_data["current_resolution"]
            agg_levels = pending_data["agg_levels"]
            report_idx = pending_data["report_idx"]

            if filetype == "html":
                graph_data_id = pending_data.get("graph_data_id")
                if not graph_data_id or graph_data_id not in download_cache:
                    return no_update, False, "Graph data expired - please restart the save."
                graph_data = download_cache.pop(graph_data_id)
                html_bytes = graph_data.get("html")
                if not html_bytes:
                    return no_update, False, "HTML data missing - please restart the save."
                return dict(content=html_bytes, filename=full_filename), False, f"Saved HTML -> {full_filename}"

            return no_update, False, f"Unsupported graph file type: {filetype}"

        except Exception as exc:
            return no_update, False, f"Save error: {exc}"

    # ------------------------------------------------------------------
    # 8) Toggle spinner visibility while saving
    # ------------------------------------------------------------------
    @app.callback(
        Output("div-std-modal-spinner", "style"),
        Input("store-std-is-saving", "data"),
    )
    def toggle_spinner_visibility(is_saving):
        return spinner_style(is_saving)

    # ------------------------------------------------------------------
    # 9) Set is_saving when Save button is clicked
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-std-is-saving", "data", allow_duplicate=True),
        Input("btn-std-modal-save", "n_clicks"),
        prevent_initial_call=True,
    )
    def on_save_button_click(n):
        return True

    # ------------------------------------------------------------------
    # 10) Clear is_saving when download completes
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-std-is-saving", "data", allow_duplicate=True),
        Input("download-std-file", "id"),
        prevent_initial_call=True,
    )
    def on_download_complete(trigger):
        return False


# ---------------------------------------------------------------------------
# Tab-specific helpers
# ---------------------------------------------------------------------------

def _build_figure(df, report, data_manager):
    """Build a Plotly figure via ``plot_report``, then optimise for Dash.

    Reads column lists from the ``report`` dict (standard report
    definitions loaded from JSON).
    """
    y1_cols = report["y1_cols"] if report["y1_cols"] else None
    y2_cols = report["y2_cols"] if report["y2_cols"] else None
    if y1_cols is None and y2_cols is None:
        df = _drop_alias_duplicate_columns(df)
    labels = report.get("labels", {})

    fig = plot_report(
        df,
        x_col="Elapsed time",
        y1_cols=y1_cols,
        y2_cols=y2_cols,
        labels=labels,
        units=data_manager.units,
        open_in_browser=False,
    )

    return finalise_figure(fig)

