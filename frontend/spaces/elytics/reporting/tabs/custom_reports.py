"""custom_reports -- Dash tab for ad-hoc custom report visualization.

Provides ``layout()`` which returns the tab's component tree and
``register_callbacks(app, data_manager)`` which wires up all interactivity.

Key features
------------
* User-selectable X-axis column (defaults to Elapsed time).
* Multi-select dropdowns for primary (Y1) and secondary (Y2) axes.
* Column lists populated dynamically from ``classify_columns()`` on
  series change.
* Two-row ribbon bar:
    Row 1 â€“ Series, X axis, Y1/Y2 column selectors.
    Row 2 â€“ Time slicer, X range slicer, Y1/Y2 range slicers, Reset.
* Time-based X (Elapsed time):
    - Time slicer â†” range slider bidirectional sync
    - Three-level dynamic aggregation (coarse / medium / fine)
    - Padded-window range slider
    - X slicer hidden (redundant).
* Non-time X (scatter):
    - Time slicer pre-filters rows (data WHERE clause)
    - Resolution selected by time-slicer span (uses aggregated means)
    - X slicer â†” range slider bidirectional sync
* Y-axis range slicers override visible axis range (input-only).
* Server-side data cache (separate from Standard Reports).
"""

import base64
import io
import json
import logging
import os
import uuid
from datetime import datetime

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.io as pio
from dash import dcc, html, no_update, callback
from dash.dependencies import Input, Output, State
from dash import callback_context

from ..model import SeriesDataManager, classify_columns
from ..tags import TAG_SERIES, tag_column
from ..visualization import (
    plot_report,
    add_band_traces,
    add_standard_traces,
    add_agg_suffix,
)
from .export_helpers import (
    build_save_modal,
    clean_rangeslider_for_export,
    download_cache,
    generate_default_download_filename,
    generate_default_graph_filename,
    get_download_file_type_options,
    get_graph_file_type_options,
    spinner_style,
    EXT_MAP,
)
from .tab_helpers import (
    ServerDataCache,
    apply_axis_overrides,
    apply_padded_window,
    apply_time_filter,
    approx_equal,
    build_res_options,
    empty_figure,
    finalise_figure,
    initial_resolution,
    load_series_data,
    pick_resolution,
    resolution_label,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server-side data cache (one instance for this tab)
# ---------------------------------------------------------------------------
_cache = ServerDataCache()


def _apply_tag_filters(df, tag_filters):
    """Apply tag filters from the store dict {col_name: [values], ...}.

    Returns filtered DataFrame.  If *tag_filters* is empty or None the
    original DataFrame is returned unchanged.
    """
    if not tag_filters or TAG_SERIES not in df.columns:
        return df
    mask = pd.Series(True, index=df.index)
    for col, allowed in tag_filters.items():
        if allowed and col in df.columns:
            mask &= df[col].isin(allowed)
    return df[mask]


def _build_filter_badges(tag_filters, tag_manager):
    """Build a list of Bootstrap badge components from the store dict."""
    if not tag_filters or tag_manager is None:
        return []
    badges = []
    defs = {tag_column(d["id"]): d["label"]
            for d in tag_manager.get_tag_definitions()}
    for col, vals in tag_filters.items():
        if not vals:
            continue
        label = defs.get(col, col)
        text = f"{label}: {', '.join(str(v) for v in vals)}"
        badges.append(
            dbc.Badge(
                [text, " \u00d7"],
                id={"type": "badge-tag-filter", "index": col},
                color="info",
                className="me-1",
                style={"cursor": "pointer", "fontSize": "0.78rem"},
            )
        )
    return badges if badges else [html.Span("None", className="text-muted small")]


def _facet_legend_from_filters(tag_manager, tag_filters, selected_series=None):
    """Build facet & legend options from the active tag-filter keys.

    Only tags the user is currently filtering on appear in the facet /
    legend dropdowns.  This keeps out 'uncategorized' facet panels and
    removes stale labels the moment a filter is cleared.
    """
    base = [{"label": "None (overlay all)", "value": "none"}]
    if tag_manager is None:
        return base, []

    parents = _as_parent_list(selected_series)
    multi_parent = len(set(parents)) > 1
    poc_opt = {"label": "PoC", "value": TAG_SERIES}
    active_cols = {col for col, vals in (tag_filters or {}).items() if vals}
    all_labels = tag_manager.get_tag_labels()          # [{label, value}, ...]
    filtered = [lbl for lbl in all_labels if lbl["value"] in active_cols]

    # Facet should offer PoC whenever multiple series are active.
    facet_opts = list(base)
    if multi_parent:
        facet_opts.append(poc_opt)
    facet_opts.extend(filtered)

    # Legend options include PoC only for multi-series comparisons.
    legend_opts = []
    if multi_parent:
        legend_opts.append(poc_opt)
    legend_opts.extend([lbl for lbl in filtered if lbl["value"] != TAG_SERIES])
    return facet_opts, legend_opts


def _build_tag_ui(tag_manager):
    """Build the compact tag-filter bar options."""
    if tag_manager is None:
        return [], [], []
    tag_defs = tag_manager.get_tag_definitions()
    tag_picker_opts = [{"label": d["label"], "value": tag_column(d["id"])}
                       for d in tag_defs]
    # Start with empty facet/legend (no filters active yet)
    facet_options = [{"label": "None (overlay all)", "value": "none"}]
    legend_options = []
    return tag_picker_opts, facet_options, legend_options


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def layout(data_manager: SeriesDataManager, tag_manager=None):
    """Return the Dash component tree for the Custom Reports tab."""

    series_options = [
        {"label": s, "value": s}
        for s in data_manager.series_defs.keys()
    ]

    tag_picker_opts, facet_options, legend_options = _build_tag_ui(tag_manager)

    return html.Div(
        style={
            "flex": "1 1 auto",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "minHeight": "0",
        },
        children=[
            # ---- stores ----
            dcc.Store(id="store-custom-series", storage_type="memory"),
            dcc.Store(id="store-custom-resolution", storage_type="memory"),
            dcc.Store(id="store-custom-agg-levels", storage_type="memory"),
            dcc.Store(id="store-custom-data-ready", storage_type="memory", data=0),
            dcc.Store(id="store-custom-save-mode", storage_type="memory"),  # "download" or "graph"
            dcc.Store(id="store-custom-pending-data", storage_type="memory"),  # Context for the pending save
            dcc.Store(id="store-custom-is-saving", storage_type="memory", data=False),
            dcc.Store(id="store-custom-tag-filters", storage_type="memory",
                      data={}),

            # ---- download/save modal + download trigger ----
            *build_save_modal("custom"),

            # ---- ribbon bar ----
            dbc.Card(
                dbc.CardBody([
                    # Row 1: selectors
                    dbc.Row(
                        [
                            dbc.Col([
                                dbc.Label("Series",
                                          className="fw-bold small mb-0"),
                                dcc.Dropdown(
                                    id="dd-custom-series",
                                    options=series_options,
                                    multi=True,
                                    placeholder="Select series\u2026",
                                    style={"fontSize": "0.85rem"},
                                ),
                            ], width=2),
                            dbc.Col([
                                dbc.Label("X axis",
                                          className="fw-bold small mb-0"),
                                dcc.Dropdown(
                                    id="dd-custom-x",
                                    clearable=False,
                                    style={"fontSize": "0.85rem"},
                                ),
                            ], width=2),
                            dbc.Col([
                                dbc.Label("Y1 columns",
                                          className="fw-bold small mb-0"),
                                dcc.Dropdown(
                                    id="dd-custom-y1",
                                    multi=True,
                                    style={"fontSize": "0.85rem"},
                                ),
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Y2 columns",
                                          className="fw-bold small mb-0"),
                                dcc.Dropdown(
                                    id="dd-custom-y2",
                                    multi=True,
                                    style={"fontSize": "0.85rem"},
                                ),
                            ], width=4),
                        ],
                        align="end",
                        className="g-2",
                    ),

                    # Row 2: range slicers + reset
                    dbc.Row(
                        [
                            # Time slicer (always visible)
                            dbc.Col([
                                dbc.Label("Time slicer [h]",
                                          className="fw-bold small mb-0"),
                                dbc.InputGroup([
                                    dbc.Input(id="input-custom-time-min",
                                              type="number", placeholder="min",
                                              size="sm"),
                                    dbc.InputGroupText("\u2013",
                                                       className="px-1"),
                                    dbc.Input(id="input-custom-time-max",
                                              type="number", placeholder="max",
                                              size="sm"),
                                ], size="sm"),
                            ], width=3),

                            # X range slicer (hidden when X = Elapsed time)
                            dbc.Col([
                                dbc.Label("X range",
                                          className="fw-bold small mb-0"),
                                dbc.InputGroup([
                                    dbc.Input(id="input-custom-x-min",
                                              type="number", placeholder="min",
                                              size="sm"),
                                    dbc.InputGroupText("\u2013",
                                                       className="px-1"),
                                    dbc.Input(id="input-custom-x-max",
                                              type="number", placeholder="max",
                                              size="sm"),
                                ], size="sm"),
                            ], id="div-custom-x-slicer", width=2,
                               style={"display": "none"}),

                            # Y1 range slicer
                            dbc.Col([
                                dbc.Label("Y1 range",
                                          className="fw-bold small mb-0"),
                                dbc.InputGroup([
                                    dbc.Input(id="input-custom-y1-min",
                                              type="number", placeholder="min",
                                              size="sm"),
                                    dbc.InputGroupText("\u2013",
                                                       className="px-1"),
                                    dbc.Input(id="input-custom-y1-max",
                                              type="number", placeholder="max",
                                              size="sm"),
                                ], size="sm"),
                            ], width=2),

                            # Y2 range slicer
                            dbc.Col([
                                dbc.Label("Y2 range",
                                          className="fw-bold small mb-0"),
                                dbc.InputGroup([
                                    dbc.Input(id="input-custom-y2-min",
                                              type="number", placeholder="min",
                                              size="sm"),
                                    dbc.InputGroupText("\u2013",
                                                       className="px-1"),
                                    dbc.Input(id="input-custom-y2-max",
                                              type="number", placeholder="max",
                                              size="sm"),
                                ], size="sm"),
                            ], width=2),

                            # Resolution override (compact)
                            dbc.Col([
                                dbc.Label("Resolution",
                                          className="fw-bold small mb-0"),
                                dcc.Dropdown(
                                    id="dd-custom-resolution",
                                    options=[{"label": "auto",
                                              "value": "auto"}],
                                    value="auto",
                                    clearable=False,
                                    style={"fontSize": "0.85rem",
                                           "minWidth": "80px"},
                                ),
                            ], width=1, style={"minWidth": "90px"}),

                            # Reset + Download + Save Graph (grouped, no-wrap)
                            dbc.Col(
                                html.Div([
                                    dbc.Button(
                                        "Reset",
                                        id="btn-custom-reset",
                                        color="dark",
                                        size="sm",
                                    ),
                                    dbc.Button(
                                        "Download",
                                        id="btn-custom-download",
                                        color="dark",
                                        size="sm",
                                    ),
                                    dbc.Button(
                                        "Save graph",
                                        id="btn-custom-save-graph",
                                        color="dark",
                                        size="sm",
                                    ),
                                ], className="d-flex gap-1 align-items-end mt-3"),
                                width="auto",
                            ),
                        ],
                        align="end",
                        className="g-2 mt-1 flex-nowrap",
                    ),
                ],
                    className="py-1 px-2 co-reporting-toolbar-body",
                ),
                className="mb-1 shadow-sm co-reporting-toolbar-card",
            ),

            # ---- Row 3: tag filters (hidden until series loaded) ---------
            html.Div(
                id="div-custom-tag-filters",
                style={"display": "none"},
                children=[
                    dbc.Card(
                        dbc.CardBody([
                            dbc.Row([
                                # Tag picker (single-select)
                                dbc.Col([
                                    dbc.Label("Filter by tag",
                                              className="fw-bold small mb-0"),
                                    dcc.Dropdown(
                                        id="dd-custom-tag-picker",
                                        options=tag_picker_opts,
                                        placeholder="Choose a tag\u2026",
                                        clearable=True,
                                        style={"fontSize": "0.85rem"},
                                    ),
                                ], width=2),
                                # Values (multi-select, depends on Tag)
                                dbc.Col([
                                    dbc.Label("Values",
                                              className="fw-bold small mb-0"),
                                    dcc.Dropdown(
                                        id="dd-custom-tag-values",
                                        multi=True,
                                        placeholder="all",
                                        style={"fontSize": "0.85rem"},
                                    ),
                                ], width=3),
                                # Active filters badge strip
                                dbc.Col([
                                    dbc.Label("Active filters",
                                              className="fw-bold small mb-0"),
                                    html.Div(
                                        id="div-custom-tag-badges",
                                        className="d-flex flex-wrap gap-1",
                                        style={"minHeight": "28px"},
                                    ),
                                ], width=3),
                                # Facet by
                                dbc.Col([
                                    dbc.Label("Facet by",
                                              className="fw-bold small mb-0"),
                                    dcc.Dropdown(
                                        id="dd-custom-facet-by",
                                        options=facet_options,
                                        value="none",
                                        clearable=False,
                                        style={"fontSize": "0.85rem"},
                                    ),
                                ], width=2),
                                # Legend by
                                dbc.Col([
                                    dbc.Label("Legend by (optional)",
                                              className="fw-bold small mb-0"),
                                    dcc.Dropdown(
                                        id="dd-custom-legend-by",
                                        options=legend_options,
                                        value=[],
                                        multi=True,
                                        style={"fontSize": "0.85rem"},
                                    ),
                                ], width=2),
                            ], align="end", className="g-2"),
                        ], className="py-1 px-2 co-reporting-toolbar-body"),
                        className="mb-1 shadow-sm co-reporting-toolbar-card",
                    ),
                ],
            ),

            # ---- status bar ----
            html.Div(
                id="status-custom-bar",
                className="text-muted small px-3 py-1",
                children="Select a series and columns to begin.",
            ),

            # ---- main graph ----
            dcc.Graph(
                id="graph-custom-report",
                style={"flex": "1 1 auto", "minHeight": "0"},
                config={
                    "displayModeBar": True,
                    "scrollZoom": True,
                    "displaylogo": False,
                },
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def register_callbacks(app, data_manager: SeriesDataManager, tag_manager=None):
    """Wire up all callbacks for the Custom Reports tab."""

    @app.callback(
        Output("btn-custom-reset", "disabled"),
        Output("btn-custom-reset", "color"),
        Output("btn-custom-download", "disabled"),
        Output("btn-custom-download", "color"),
        Output("btn-custom-save-graph", "disabled"),
        Output("btn-custom-save-graph", "color"),
        Input("store-custom-series", "data"),
        Input("graph-custom-report", "figure"),
        Input("dd-custom-y1", "value"),
        Input("dd-custom-y2", "value"),
        Input("input-custom-time-min", "value"),
        Input("input-custom-time-max", "value"),
        Input("input-custom-x-min", "value"),
        Input("input-custom-x-max", "value"),
        Input("input-custom-y1-min", "value"),
        Input("input-custom-y1-max", "value"),
        Input("input-custom-y2-min", "value"),
        Input("input-custom-y2-max", "value"),
        Input("dd-custom-resolution", "value"),
        prevent_initial_call=False,
    )
    def set_custom_button_states(current_series, figure,
                                 y1_cols, y2_cols,
                                 tmin, tmax, xmin, xmax,
                                 y1min, y1max, y2min, y2max,
                                 resolution):
        has_series = bool(current_series)
        has_y = bool(y1_cols) or bool(y2_cols)
        has_fig = bool(figure and figure.get("data"))

        reset_useful = any(v is not None for v in [tmin, tmax, xmin, xmax, y1min, y1max, y2min, y2max]) or (resolution not in (None, "auto"))
        reset_disabled = not reset_useful
        reset_color = "secondary" if reset_disabled else "dark"

        download_disabled = not (has_series and has_y)
        download_color = "secondary" if download_disabled else "dark"

        save_graph_disabled = not (has_series and has_fig)
        save_graph_color = "secondary" if save_graph_disabled else "dark"

        return (
            reset_disabled,
            reset_color,
            download_disabled,
            download_color,
            save_graph_disabled,
            save_graph_color,
        )

    @app.callback(
        Output("dd-custom-series", "options"),
        Output("dd-custom-series", "value"),
        Input("store-series-refresh", "data"),
        State("dd-custom-series", "value"),
        prevent_initial_call=False,
    )
    def refresh_custom_series_dropdown(_refresh_tick, current_value):
        series_options = [
            {"label": s, "value": s}
            for s in data_manager.series_defs.keys()
        ]
        valid_values = {o["value"] for o in series_options}
        current_list = current_value if isinstance(current_value, list) else (
            [current_value] if current_value else [])
        kept = [v for v in current_list if v in valid_values]
        return series_options, kept or None

    # ------------------------------------------------------------------
    # 0) Toggle X-slicer visibility based on X-axis selection
    # ------------------------------------------------------------------
    @app.callback(
        Output("div-custom-x-slicer", "style"),
        Input("dd-custom-x", "value"),
    )
    def toggle_x_slicer(x_col):
        if x_col == "Elapsed time" or not x_col:
            return {"display": "none"}
        return {}

    # ------------------------------------------------------------------
    # 1) Series changed â†’ load data, populate column dropdowns,
    #    discover available tag values
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-custom-series", "data"),
        Output("store-custom-agg-levels", "data"),
        Output("store-custom-data-ready", "data"),
        Output("dd-custom-x", "options"),
        Output("dd-custom-x", "value"),
        Output("dd-custom-y1", "options"),
        Output("dd-custom-y1", "value"),
        Output("dd-custom-y2", "options"),
        Output("dd-custom-y2", "value"),
        Output("dd-custom-resolution", "options"),
        Output("dd-custom-resolution", "value"),
        Output("status-custom-bar", "children"),
        Output("div-custom-tag-filters", "style"),
        Output("store-custom-tag-filters", "data"),
        Output("dd-custom-tag-picker", "options"),
        Output("dd-custom-facet-by", "options"),
        Output("dd-custom-legend-by", "options"),
        Input("dd-custom-series", "value"),
        State("store-custom-series", "data"),
        State("store-custom-data-ready", "data"),
        State("dd-custom-x", "value"),
        State("dd-custom-y1", "value"),
        State("dd-custom-y2", "value"),
        State("store-custom-tag-filters", "data"),
    )
    def on_series_changed(selected_series, prev_series_list, prev_trigger,
                          prev_x, prev_y1, prev_y2,
                          prev_tag_filters):
        # 17 outputs: 12 base + style + filters + picker + facet + legend
        N_OUT = 17
        # Normalise to lists
        selected = selected_series if isinstance(selected_series, list) else (
            [selected_series] if selected_series else [])
        prev = prev_series_list if isinstance(prev_series_list, list) else (
            [prev_series_list] if prev_series_list else [])

        if not selected:
            # Unload everything
            for s in prev:
                p = SeriesDataManager._parse_agg_name(s)[0]
                _cache.drop_series(p)
                for key in list(data_manager.loaded_series.keys()):
                    if SeriesDataManager._parse_agg_name(key)[0] == p:
                        data_manager.unload_series(key)
            return ((no_update,) * 12
                    + ({"display": "none"}, {}, no_update, no_update,
                       no_update))

        prev_set = set(prev)
        sel_set = set(selected)

        # Unload removed series
        for s in prev_set - sel_set:
            p = SeriesDataManager._parse_agg_name(s)[0]
            _cache.drop_series(p)
            for key in list(data_manager.loaded_series.keys()):
                if SeriesDataManager._parse_agg_name(key)[0] == p:
                    data_manager.unload_series(key)

        # Load newly-added series
        all_agg: dict = {}
        total_rows = 0
        for s in selected:
            parent = SeriesDataManager._parse_agg_name(s)[0]
            if s in sel_set - prev_set:
                parent, agg_meta, n_rows, _, _ = load_series_data(
                    _cache, data_manager, s, None)
                log.info("Loaded %s: %d raw rows", parent, n_rows)
            else:
                sdef = data_manager.series_defs.get(parent, {})
                intervals = sorted(sdef.get("aggregations", []), reverse=True)
                agg_meta = [{"interval": iv, "name": f"{parent}_agg{iv}min"}
                            for iv in intervals
                            if _cache.get(parent, f"agg{iv}") is not None]
                raw = _cache.get(parent, "raw")
                n_rows = len(raw) if raw is not None else 0
            all_agg[parent] = agg_meta
            total_rows += n_rows

        # Column intersection across all selected series
        x_sets, y_sets = [], []
        for s in selected:
            parent = SeriesDataManager._parse_agg_name(s)[0]
            raw_df = _cache.get(parent, "raw")
            xb, yb = classify_columns(raw_df)
            x_sets.append(set(xb))
            y_sets.append(set(yb))
        common_x = sorted(set.intersection(*x_sets)) if x_sets else []
        common_y = sorted(set.intersection(*y_sets)) if y_sets else []

        x_options = [{"label": "Elapsed time", "value": "Elapsed time"}]
        x_options += [{"label": c, "value": c} for c in common_x]
        y_options = [{"label": c, "value": c} for c in common_y]

        common_y_set = set(common_y)
        all_x_values = {"Elapsed time"} | set(common_x)

        new_x = prev_x if prev_x and prev_x in all_x_values else "Elapsed time"

        kept_y1 = [c for c in (prev_y1 or []) if c in common_y_set]
        new_y1 = kept_y1 if kept_y1 else no_update if prev_y1 is None else []

        kept_y2 = [c for c in (prev_y2 or []) if c in common_y_set]
        new_y2 = kept_y2 if kept_y2 else no_update if prev_y2 is None else []

        # Common aggregation levels
        all_intervals = [set(a["interval"] for a in metas)
                         for metas in all_agg.values()]
        common_intervals = sorted(
            set.intersection(*all_intervals) if all_intervals else set(),
            reverse=True)
        common_agg_meta = [{"interval": iv, "name": f"common_agg{iv}min"}
                           for iv in common_intervals]
        res_options = build_res_options(common_agg_meta)

        n_series = len(selected)
        labels = ", ".join(SeriesDataManager._parse_agg_name(s)[0]
                           for s in selected)
        status = f"Loaded {n_series} series ({labels})  \u2022  {total_rows:,} raw rows"

        # Discover available tag values for each tag definition
        tag_defs = tag_manager.get_tag_definitions() if tag_manager else []
        avail = {}
        if tag_manager is not None and tag_defs:
            tag_frames = []
            for s in selected:
                parent = SeriesDataManager._parse_agg_name(s)[0]
                raw_df = _cache.get(parent, "agg15")
                if raw_df is None or raw_df.empty:
                    raw_df = _cache.get(parent, "raw")
                if raw_df is not None and not raw_df.empty:
                    tag_frames.append(tag_manager.apply_tags(raw_df, parent))
            if tag_frames:
                tag_combined = pd.concat(tag_frames, ignore_index=True)
                for defn in tag_defs:
                    col = tag_column(defn["id"])
                    if col in tag_combined.columns:
                        vals = sorted(
                            str(v) for v in tag_combined[col].dropna().unique())
                        avail[col] = vals
            filter_style = {}
        else:
            filter_style = {"display": "none"}

        # Prune previous filter selections
        prev_tag_filters = prev_tag_filters or {}
        pruned_filters = {}
        for col, vals in prev_tag_filters.items():
            if col in avail and vals:
                kept = [v for v in vals if v in avail[col]]
                if kept:
                    pruned_filters[col] = kept

        # Dynamic tag picker / facet / legend options
        tag_picker_opts = [{"label": d["label"], "value": tag_column(d["id"])}
                           for d in tag_defs]
        facet_options, legend_options = _facet_legend_from_filters(
            tag_manager, pruned_filters, selected)

        trigger = (prev_trigger or 0) + 1
        return (
            selected,
            {"per_parent": {SeriesDataManager._parse_agg_name(s)[0]:
                            all_agg[SeriesDataManager._parse_agg_name(s)[0]]
                            for s in selected},
             "common": common_agg_meta},
            trigger,
            x_options,
            new_x,
            y_options,
            new_y1,
            y_options,
            new_y2,
            res_options,
            "auto",
            status,
            filter_style,
            pruned_filters,
            tag_picker_opts,
            facet_options,
            legend_options,
        )

    # ------------------------------------------------------------------
    # 1b) Tag picker changed â†’ populate Values dropdown (live from cache)
    # ------------------------------------------------------------------
    @app.callback(
        Output("dd-custom-tag-values", "options"),
        Output("dd-custom-tag-values", "value"),
        Input("dd-custom-tag-picker", "value"),
        State("store-custom-series", "data"),
        State("store-custom-tag-filters", "data"),
    )
    def on_tag_picker(tag_col, current_series, tag_filters):
        if not tag_col or not current_series:
            return [], None
        parents = _as_parent_list(current_series)
        frames = []
        for p in parents:
            raw_df = _cache.get(p, "agg15")
            if raw_df is None or raw_df.empty:
                raw_df = _cache.get(p, "raw")
            if raw_df is not None and not raw_df.empty and tag_manager is not None:
                frames.append(tag_manager.apply_tags(raw_df, p))
        if not frames:
            return [], None
        combined = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
        if tag_col not in combined.columns:
            return [], None
        vals = sorted(str(v) for v in combined[tag_col].dropna().unique())
        opts = [{"label": v, "value": v} for v in vals]
        current = (tag_filters or {}).get(tag_col, [])
        return opts, current or None

    # ------------------------------------------------------------------
    # 1c) Values changed â†’ update tag filter store + badges
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-custom-tag-filters", "data", allow_duplicate=True),
        Output("div-custom-tag-badges", "children"),
        Input("dd-custom-tag-values", "value"),
        State("dd-custom-tag-picker", "value"),
        State("store-custom-tag-filters", "data"),
        prevent_initial_call=True,
    )
    def on_tag_values_changed(values, tag_col, tag_filters):
        tag_filters = dict(tag_filters) if tag_filters else {}
        if tag_col:
            if values:
                tag_filters[tag_col] = list(values)
            else:
                tag_filters.pop(tag_col, None)
        return tag_filters, _build_filter_badges(tag_filters, tag_manager)

    # ------------------------------------------------------------------
    # 1d) Badge click â†’ remove that tag's filter
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-custom-tag-filters", "data", allow_duplicate=True),
        Output("div-custom-tag-badges", "children", allow_duplicate=True),
        Output("dd-custom-tag-values", "value", allow_duplicate=True),
        Output("dd-custom-tag-picker", "value", allow_duplicate=True),
        Input({"type": "badge-tag-filter", "index": dash.ALL}, "n_clicks"),
        State("store-custom-tag-filters", "data"),
        State("dd-custom-tag-picker", "value"),
        prevent_initial_call=True,
    )
    def on_badge_click(n_clicks_list, tag_filters, current_picker):
        tag_filters = dict(tag_filters) if tag_filters else {}
        ctx = callback_context
        if not ctx.triggered:
            return no_update, no_update, no_update, no_update
        prop_id = ctx.triggered[0]["prop_id"]
        if not ctx.triggered[0]["value"]:
            return no_update, no_update, no_update, no_update
        try:
            id_dict = json.loads(prop_id.rsplit(".", 1)[0])
            clicked_col = id_dict["index"]
        except Exception:
            return no_update, no_update, no_update, no_update
        tag_filters.pop(clicked_col, None)
        badges = _build_filter_badges(tag_filters, tag_manager)
        new_vals = None if current_picker == clicked_col else no_update
        new_picker = None if current_picker == clicked_col else no_update
        return tag_filters, badges, new_vals, new_picker

    # ------------------------------------------------------------------
    # 1e) Filter store changed â†’ rebuild badges + update facet/legend
    # ------------------------------------------------------------------
    @app.callback(
        Output("div-custom-tag-badges", "children", allow_duplicate=True),
        Output("dd-custom-facet-by", "options", allow_duplicate=True),
        Output("dd-custom-facet-by", "value", allow_duplicate=True),
        Output("dd-custom-legend-by", "options", allow_duplicate=True),
        Output("dd-custom-legend-by", "value", allow_duplicate=True),
        Input("store-custom-tag-filters", "data"),
        State("dd-custom-series", "value"),
        Input("dd-custom-facet-by", "value"),
        State("dd-custom-legend-by", "value"),
        prevent_initial_call=True,
    )
    def on_filters_changed(tag_filters, selected_series, cur_facet, cur_legend):
        badges = _build_filter_badges(tag_filters, tag_manager)
        facet_opts, legend_opts = _facet_legend_from_filters(
            tag_manager, tag_filters, selected_series)
        valid_facet_vals = {o["value"] for o in facet_opts}
        new_facet = cur_facet if cur_facet in valid_facet_vals else "none"

        # Facet dimension cannot simultaneously be a legend dimension.
        if new_facet and new_facet != "none":
            legend_opts = [o for o in legend_opts if o["value"] != new_facet]

        valid_legend_vals = {o["value"] for o in legend_opts}
        new_legend = [v for v in (cur_legend or []) if v in valid_legend_vals]

        # Show contextual defaults as selected values in the dropdown, not just
        # implicit in render logic. This avoids the select/deselect roundtrip.
        if not new_legend:
            facet_for_default = None if new_facet == "none" else new_facet
            default_legend = _effective_legend_by(
                [], facet_for_default, tag_filters, selected_series
            )
            new_legend = [v for v in default_legend if v in valid_legend_vals]

        return badges, facet_opts, new_facet, legend_opts, new_legend or no_update

    # ------------------------------------------------------------------
    # 2) Data ready / column / slicer changed â†’ render figure
    # ------------------------------------------------------------------
    @app.callback(
        Output("graph-custom-report", "figure"),
        Output("store-custom-resolution", "data"),
        Input("store-custom-data-ready", "data"),
        Input("dd-custom-x", "value"),
        Input("dd-custom-y1", "value"),
        Input("dd-custom-y2", "value"),
        Input("input-custom-time-min", "value"),
        Input("input-custom-time-max", "value"),
        Input("input-custom-x-min", "value"),
        Input("input-custom-x-max", "value"),
        Input("input-custom-y1-min", "value"),
        Input("input-custom-y1-max", "value"),
        Input("input-custom-y2-min", "value"),
        Input("input-custom-y2-max", "value"),
        Input("dd-custom-resolution", "value"),
        Input("store-custom-tag-filters", "data"),
        Input("dd-custom-facet-by", "value"),
        Input("dd-custom-legend-by", "value"),
        State("store-custom-series", "data"),
        State("store-custom-agg-levels", "data"),
    )
    def render_report(
        data_trigger, x_col, y1_cols, y2_cols,
        time_min, time_max,
        x_min, x_max,
        y1_min, y1_max,
        y2_min, y2_max,
        res_override,
        tag_filters,
        facet_by, legend_by,
        current_series, agg_levels,
    ):
        if not current_series:
            return empty_figure("Select a series."), no_update
        if not y1_cols and not y2_cols:
            return empty_figure("Select at least one Y column."), no_update

        parents = _as_parent_list(current_series)
        x_col = x_col or "Elapsed time"
        is_time_x = (x_col == "Elapsed time")
        per_parent = agg_levels.get("per_parent", {}) if isinstance(agg_levels, dict) else {}
        common_agg = agg_levels.get("common", agg_levels) if isinstance(agg_levels, dict) else agg_levels

        # Resolution: override or auto
        res_override = res_override or "auto"
        if res_override != "auto":
            resolution = res_override
        else:
            spans = [_cache.slicer_span_seconds(p, time_min, time_max)
                     for p in parents]
            slicer_span = max((s for s in spans if s is not None), default=None)
            resolution = pick_resolution(slicer_span, common_agg)

        frames = []
        for parent in parents:
            p_agg = per_parent.get(parent, common_agg)
            pdf = _cache.get(parent, resolution)
            if pdf is None or pdf.empty:
                pdf, _ = _cache.fallback_data(parent, resolution, p_agg)
            if pdf is not None and not pdf.empty:
                if tag_manager is not None:
                    pdf = tag_manager.apply_tags(pdf, parent)
                frames.append(pdf)
        if not frames:
            return empty_figure("No data available."), resolution
        df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]

        if is_time_x:
            df = apply_padded_window(df, time_min, time_max)
        else:
            df = apply_time_filter(df, time_min, time_max)

        if df.empty:
            return (
                empty_figure("No data in the selected time range."),
                resolution,
            )

        # Apply tag filters
        df = _apply_tag_filters(df, tag_filters)
        if df.empty:
            return empty_figure("No data after filtering."), resolution

        facet_col = facet_by if (facet_by and facet_by != "none"
                                 and facet_by in df.columns) else None
        eff_legend = _effective_legend_by(legend_by, facet_col, tag_filters,
                          current_series)
        grp = _build_legend_col(df, eff_legend)
        facet_order = None
        if facet_col and isinstance(tag_filters, dict):
            facet_order = tag_filters.get(facet_col)
        fig = _build_figure(df, x_col, y1_cols, y2_cols, data_manager,
                            group_col=grp, facet_col=facet_col,
                            facet_order=facet_order)

        # X-axis zoom
        if is_time_x:
            if time_min is not None and time_max is not None:
                fig.update_xaxes(range=[float(time_min), float(time_max)])
        else:
            if x_min is not None and x_max is not None:
                fig.update_xaxes(range=[float(x_min), float(x_max)])

        # Y-axis range overrides
        apply_axis_overrides(fig, y1_min, y1_max, y2_min, y2_max)

        return fig, resolution

    # ------------------------------------------------------------------
    # 3) Zoom/pan â†’ switch resolution + sync slicer
    #    Time-based X  â†’ syncs time slicer, handles resolution switch
    #    Non-time X    â†’ syncs X slicer only
    # ------------------------------------------------------------------
    NO_UPD_7 = (no_update,) * 7

    @app.callback(
        Output("graph-custom-report", "figure", allow_duplicate=True),
        Output("store-custom-resolution", "data", allow_duplicate=True),
        Output("status-custom-bar", "children", allow_duplicate=True),
        Output("input-custom-time-min", "value", allow_duplicate=True),
        Output("input-custom-time-max", "value", allow_duplicate=True),
        Output("input-custom-x-min", "value", allow_duplicate=True),
        Output("input-custom-x-max", "value", allow_duplicate=True),
        Input("graph-custom-report", "relayoutData"),
        State("store-custom-resolution", "data"),
        State("store-custom-agg-levels", "data"),
        State("store-custom-series", "data"),
        State("dd-custom-x", "value"),
        State("dd-custom-y1", "value"),
        State("dd-custom-y2", "value"),
        State("input-custom-time-min", "value"),
        State("input-custom-time-max", "value"),
        State("input-custom-x-min", "value"),
        State("input-custom-x-max", "value"),
        State("dd-custom-resolution", "value"),
        State("store-custom-tag-filters", "data"),
        State("dd-custom-facet-by", "value"),
        State("dd-custom-legend-by", "value"),
        prevent_initial_call=True,
    )
    def on_zoom(
        relayout_data, current_resolution,
        agg_levels, current_series,
        x_col, y1_cols, y2_cols,
        time_min, time_max,
        x_slicer_min, x_slicer_max,
        res_override,
        tag_filters,
        facet_by, legend_by,
    ):
        if not relayout_data or not current_series:
            return NO_UPD_7

        x_col = x_col or "Elapsed time"
        is_time_x = (x_col == "Elapsed time")
        parents = _as_parent_list(current_series)
        parent = parents[0] if parents else None
        if not parent:
            return NO_UPD_7

        per_parent = agg_levels.get("per_parent", {}) if isinstance(agg_levels, dict) else {}
        common_agg = agg_levels.get("common", agg_levels) if isinstance(agg_levels, dict) else agg_levels

        # Extract visible x-range â€” handle both key formats
        x0 = relayout_data.get("xaxis.range[0]")
        x1 = relayout_data.get("xaxis.range[1]")
        if x0 is None and x1 is None:
            xrange = relayout_data.get("xaxis.range")
            if isinstance(xrange, (list, tuple)) and len(xrange) == 2:
                x0, x1 = xrange

        # ==============================================================
        # Branch A: time-based X  â†’  time-slicer sync + resolution
        # ==============================================================
        if is_time_x:
            new_tmin = no_update
            new_tmax = no_update

            if relayout_data.get("xaxis.autorange"):
                desired = initial_resolution(common_agg)
                new_tmin = None
                new_tmax = None
            elif x0 is not None and x1 is not None:
                x0_f, x1_f = float(x0), float(x1)
                span_seconds = (x1_f - x0_f) * 3600
                desired = pick_resolution(span_seconds, common_agg)
                new_tmin = round(x0_f, 2)
                new_tmax = round(x1_f, 2)
            else:
                return NO_UPD_7

            # When user has forced a resolution, skip automatic switching
            res_override = res_override or "auto"
            if res_override != "auto":
                desired = res_override

            slicer_unchanged = (
                approx_equal(new_tmin, time_min)
                and approx_equal(new_tmax, time_max)
            )
            if desired == current_resolution and slicer_unchanged:
                return NO_UPD_7

            # Slicer changed, resolution same â†’ sync only
            if desired == current_resolution:
                return (no_update, no_update, no_update,
                        new_tmin, new_tmax,
                        no_update, no_update)

            # Resolution changed â†’ rebuild figure
            if not y1_cols and not y2_cols:
                return NO_UPD_7

            eff_tmin = new_tmin if new_tmin is not no_update else time_min
            eff_tmax = new_tmax if new_tmax is not no_update else time_max

            zoom_frames = []
            for p in parents:
                p_agg = per_parent.get(p, common_agg)
                zdf = _cache.get(p, desired)
                if zdf is None or zdf.empty:
                    zdf, _ = _cache.fallback_data(p, desired, p_agg)
                if zdf is not None and not zdf.empty:
                    if tag_manager is not None:
                        zdf = tag_manager.apply_tags(zdf, p)
                    zoom_frames.append(zdf)
            if not zoom_frames:
                return NO_UPD_7
            df = pd.concat(zoom_frames, ignore_index=True) if len(zoom_frames) > 1 else zoom_frames[0]

            df = apply_padded_window(df, eff_tmin, eff_tmax)
            if df.empty:
                return (
                    empty_figure("No data in range."),
                    desired,
                    f"Resolution: {resolution_label(desired)} (no data)",
                    new_tmin, new_tmax,
                    no_update, no_update,
                )

            # Apply tag filters
            df = _apply_tag_filters(df, tag_filters)
            if df.empty:
                return (
                    empty_figure("No data after filtering."),
                    desired,
                    f"Resolution: {resolution_label(desired)} (filtered out)",
                    new_tmin, new_tmax,
                    no_update, no_update,
                )

            fc = facet_by if (facet_by and facet_by != "none"
                              and facet_by in df.columns) else None
            eff_legend = _effective_legend_by(legend_by, fc, tag_filters,
                                              current_series)
            grp = _build_legend_col(df, eff_legend)
            fig = _build_figure(df, x_col, y1_cols, y2_cols, data_manager,
                                group_col=grp, facet_col=fc)
            if x0 is not None and x1 is not None:
                fig.update_xaxes(range=[float(x0), float(x1)])

            res_label = resolution_label(desired)
            status = f"Resolution: {res_label}  \u2022  {len(df):,} pts"
            return (fig, desired, status,
                    new_tmin, new_tmax,
                    no_update, no_update)

        # ==============================================================
        # Branch B: non-time X  â†’  X-slicer sync only (no res switch)
        # ==============================================================
        new_xmin = no_update
        new_xmax = no_update

        if relayout_data.get("xaxis.autorange"):
            new_xmin = None
            new_xmax = None
        elif x0 is not None and x1 is not None:
            new_xmin = round(float(x0), 4)
            new_xmax = round(float(x1), 4)
        else:
            return NO_UPD_7

        slicer_unchanged = (
            approx_equal(new_xmin, x_slicer_min)
            and approx_equal(new_xmax, x_slicer_max)
        )
        if slicer_unchanged:
            return NO_UPD_7

        return (no_update, no_update, no_update,
                no_update, no_update,
                new_xmin, new_xmax)

    # ------------------------------------------------------------------
    # 4) Reset â†’ clear all slicer inputs
    # ------------------------------------------------------------------
    @app.callback(
        Output("input-custom-time-min", "value", allow_duplicate=True),
        Output("input-custom-time-max", "value", allow_duplicate=True),
        Output("input-custom-x-min", "value", allow_duplicate=True),
        Output("input-custom-x-max", "value", allow_duplicate=True),
        Output("input-custom-y1-min", "value", allow_duplicate=True),
        Output("input-custom-y1-max", "value", allow_duplicate=True),
        Output("input-custom-y2-min", "value", allow_duplicate=True),
        Output("input-custom-y2-max", "value", allow_duplicate=True),
        Output("dd-custom-resolution", "value", allow_duplicate=True),
        Input("btn-custom-reset", "n_clicks"),
        prevent_initial_call=True,
    )
    def on_reset(n_clicks):
        return (None,) * 8 + ("auto",)

    # ------------------------------------------------------------------
    # 5) Download Selection â†’ open modal to choose filename/type
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-custom-save", "is_open"),
        Output("store-custom-save-mode", "data"),
        Output("store-custom-pending-data", "data"),
        Output("input-custom-save-filename", "value"),
        Output("dd-custom-save-filetype", "options"),
        Output("dd-custom-save-filetype", "value"),
        Output("status-custom-bar", "children", allow_duplicate=True),
        Output("store-custom-is-saving", "data", allow_duplicate=True),
        Input("btn-custom-download", "n_clicks"),
        State("store-custom-series", "data"),
        State("store-custom-agg-levels", "data"),
        State("dd-custom-x", "value"),
        State("dd-custom-y1", "value"),
        State("dd-custom-y2", "value"),
        State("input-custom-time-min", "value"),
        State("input-custom-time-max", "value"),
        State("dd-custom-resolution", "value"),
        State("store-custom-tag-filters", "data"),
        prevent_initial_call=True,
    )
    def on_download_open_modal(n, series_name, agg_levels, x_col, y1_cols, y2_cols,
                               time_min, time_max, res_override, tag_filters):
        if not series_name:
            return no_update, no_update, no_update, no_update, no_update, no_update, "No series loaded â€“ cannot download.", False
        y1_cols = y1_cols or []
        y2_cols = y2_cols or []
        if not y1_cols and not y2_cols:
            return no_update, no_update, no_update, no_update, no_update, no_update, "Select at least one Y column before downloading.", False

        parents = _as_parent_list(series_name)
        per_parent = agg_levels.get("per_parent", {}) if isinstance(agg_levels, dict) else {}
        common_agg = agg_levels.get("common", agg_levels) if isinstance(agg_levels, dict) else agg_levels
        res_override = res_override or "auto"
        resolution = res_override if res_override != "auto" else "raw"

        dl_frames = []
        for parent in parents:
            p_agg = per_parent.get(parent, common_agg)
            tdf = _cache.get(parent, resolution)
            if tdf is None or tdf.empty:
                tdf, _ = _cache.fallback_data(parent, resolution, p_agg)
            if tdf is not None and not tdf.empty:
                if tag_manager is not None:
                    tdf = tag_manager.apply_tags(tdf, parent)
                dl_frames.append(tdf)
        if not dl_frames:
            return no_update, no_update, no_update, no_update, no_update, no_update, f"No data available at resolution '{resolution}'.", False
        df = pd.concat(dl_frames, ignore_index=True) if len(dl_frames) > 1 else dl_frames[0]

        # Apply tag filters
        df = _apply_tag_filters(df, tag_filters)
        if df.empty:
            return no_update, no_update, no_update, no_update, no_update, no_update, "No data after filtering.", False

        # Store context for later use in modal save
        time_column = "Elapsed time"
        x_col_val = x_col or time_column
        sel_cols = []
        # Include tag series column so user can distinguish series in the CSV
        if TAG_SERIES in df.columns:
            sel_cols.append(TAG_SERIES)
        if x_col_val != time_column:
            sel_cols.append(x_col_val)
        for c in y1_cols + y2_cols:
            if c not in sel_cols:
                sel_cols.append(c)

        # Filter sel_cols to only include columns that exist in the actual dataframe at this resolution
        available_cols = list(df.columns)
        sel_cols_valid = []
        
        for col in sel_cols:
            if col in available_cols:
                sel_cols_valid.append(col)
            else:
                agg_suffixes = ["_mean", "_max", "_min", "_std", "_count"]
                for suffix in agg_suffixes:
                    agg_col = f"{col}{suffix}"
                    if agg_col in available_cols and agg_col not in sel_cols_valid:
                        sel_cols_valid.append(agg_col)

        time_slicer = None
        if time_min is not None and time_max is not None:
            try:
                time_slicer = (float(time_min) * 3600, float(time_max) * 3600)
            except (TypeError, ValueError):
                pass

        download_df_id = str(uuid.uuid4())
        download_cache[download_df_id] = df

        pending_data = {
            "mode": "download",
            "download_df_id": download_df_id,
            "sel_cols": sel_cols_valid,
            "time_column": time_column,
            "time_slicer": time_slicer,
            "resolution": resolution,
        }

        file_label = "_".join(_as_parent_list(series_name))
        default_filename = generate_default_download_filename(file_label)
        file_type_opts = get_download_file_type_options()

        return True, "download", pending_data, default_filename, file_type_opts, "csv", "", False
    # ------------------------------------------------------------------
    # 6) Save Graph â†’ open modal to choose filename/type
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-custom-save", "is_open", allow_duplicate=True),
        Output("store-custom-save-mode", "data", allow_duplicate=True),
        Output("store-custom-pending-data", "data", allow_duplicate=True),
        Output("input-custom-save-filename", "value", allow_duplicate=True),
        Output("dd-custom-save-filetype", "options", allow_duplicate=True),
        Output("dd-custom-save-filetype", "value", allow_duplicate=True),
        Output("status-custom-bar", "children", allow_duplicate=True),
        Output("store-custom-is-saving", "data", allow_duplicate=True),
        Input("btn-custom-save-graph", "n_clicks"),
        State("graph-custom-report", "figure"),
        State("store-custom-series", "data"),
        State("store-custom-agg-levels", "data"),
        State("dd-custom-x", "value"),
        State("dd-custom-y1", "value"),
        State("dd-custom-y2", "value"),
        State("input-custom-time-min", "value"),
        State("input-custom-time-max", "value"),
        State("dd-custom-resolution", "value"),
        State("store-custom-tag-filters", "data"),
        State("dd-custom-facet-by", "value"),
        State("dd-custom-legend-by", "value"),
        prevent_initial_call=True,
    )
    def on_save_graph_open_modal(n, figure_dict, series_name, agg_levels,
                                 x_col, y1_cols, y2_cols, time_min, time_max,
                                 res_override, tag_filters, facet_by, legend_by):
        if not series_name or not figure_dict:
            return no_update, no_update, no_update, no_update, no_update, no_update, "No chart to save â€“ load a series first.", False

        graph_data_id = str(uuid.uuid4())

        try:
            clean_rangeslider_for_export(figure_dict)
            html_bytes = pio.to_html(figure_dict, include_plotlyjs='cdn')
        except Exception as fig_err:
            return no_update, no_update, no_update, no_update, no_update, no_update, f"Failed to prepare graph for export: {str(fig_err)[:100]}", False

        download_cache[graph_data_id] = {
            "html": html_bytes,
            "series_name": series_name,
        }

        pending_data = {
            "mode": "graph",
            "graph_data_id": graph_data_id,
        }

        file_label = "_".join(_as_parent_list(series_name))
        default_filename = generate_default_graph_filename(file_label)
        file_type_opts = get_graph_file_type_options()

        return True, "graph", pending_data, default_filename, file_type_opts, "html", "", False

    # ------------------------------------------------------------------
    # 7) Modal cancel button
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-custom-save", "is_open", allow_duplicate=True),
        Input("btn-custom-modal-cancel", "n_clicks"),
        prevent_initial_call=True,
    )
    def on_modal_cancel(n):
        return False

    # ------------------------------------------------------------------
    # 8) Modal save button â†’ generate file and trigger download
    # ------------------------------------------------------------------
    @callback(
        Output("download-custom-file", "data"),
        Output("modal-custom-save", "is_open", allow_duplicate=True),
        Output("status-custom-bar", "children", allow_duplicate=True),
        Input("btn-custom-modal-save", "n_clicks"),
        State("input-custom-save-filename", "value"),
        State("dd-custom-save-filetype", "value"),
        State("store-custom-save-mode", "data"),
        State("store-custom-pending-data", "data"),
        prevent_initial_call=True,
        background=True,
        running=[
            (Output("store-custom-is-saving", "data"), True, False),
        ],
    )
    def on_modal_save(n, filename, filetype, save_mode, pending_data):
        if not filename or not filetype or not save_mode or not pending_data:
            return no_update, False, "Invalid save parameters."

        try:
            filename_clean = filename.strip()
            if not filename_clean:
                return no_update, False, "Filename cannot be empty."

            ext = EXT_MAP.get(filetype, ".txt")
            full_filename = f"{filename_clean}{ext}"

            if save_mode == "download":
                try:
                    download_df_id = pending_data.get("download_df_id")
                    if not download_df_id or download_df_id not in download_cache:
                        return no_update, False, "Download data expired â€“ please restart the download."
                    df = download_cache.pop(download_df_id)

                    sel_cols = pending_data["sel_cols"]
                    time_column = pending_data["time_column"]
                    time_slicer = pending_data["time_slicer"]
                    resolution = pending_data["resolution"]

                    df_out = df.copy()
                    if time_slicer:
                        t_min, t_max = time_slicer
                        df_out = df_out[(df_out[time_column] >= t_min) & (df_out[time_column] <= t_max)]
                    cols_to_export = [time_column] + [c for c in sel_cols if c in df_out.columns]

                    if filetype == "csv":
                        csv_data = df_out[cols_to_export].to_csv(index=False)
                        res_label = resolution if resolution != "raw" else "raw (1 s)"
                        return dict(content=csv_data, filename=full_filename), False, f"Downloaded [{res_label}] â†’ {full_filename}"
                except Exception as load_err:
                    return no_update, False, f"Download error: {type(load_err).__name__}: {str(load_err)[:200]}"

            elif save_mode == "graph":
                graph_data_id = pending_data.get("graph_data_id")
                if not graph_data_id or graph_data_id not in download_cache:
                    return no_update, False, "Graph data expired â€“ please restart the save."
                graph_data = download_cache.pop(graph_data_id)

                if filetype == "html":
                    html_bytes = graph_data.get("html")
                    if not html_bytes:
                        return no_update, False, "HTML data missing â€“ please restart the save."
                    return dict(content=html_bytes, filename=full_filename), False, f"Saved HTML â†’ {full_filename}"

                elif filetype in ("pdf", "png", "jpg"):
                    return no_update, False, f"Image export ({filetype}) not yet implemented in this save mode."

        except Exception as exc:
            return no_update, False, f"Save error: {exc}"

    # ------------------------------------------------------------------
    # 9) Toggle spinner visibility while saving
    # ------------------------------------------------------------------
    @app.callback(
        Output("div-custom-modal-spinner", "style"),
        Input("store-custom-is-saving", "data"),
    )
    def toggle_spinner_visibility(is_saving):
        return spinner_style(is_saving)

    # ------------------------------------------------------------------
    # 10) Set is_saving when Save button is clicked
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-custom-is-saving", "data", allow_duplicate=True),
        Input("btn-custom-modal-save", "n_clicks"),
        prevent_initial_call=True,
    )
    def on_save_button_click(n):
        return True

    # ------------------------------------------------------------------
    # 11) Clear is_saving when download completes
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-custom-is-saving", "data", allow_duplicate=True),
        Input("download-custom-file", "id"),
        prevent_initial_call=True,
    )
    def on_download_complete(trigger):
        return False

# ---------------------------------------------------------------------------
# Tab-specific helpers
# ---------------------------------------------------------------------------

def _as_parent_list(series_value):
    """Normalise the stored series value to a list of parent names."""
    if not series_value:
        return []
    items = series_value if isinstance(series_value, list) else [series_value]
    return [SeriesDataManager._parse_agg_name(s)[0] for s in items]


def _build_legend_col(df, legend_by):
    """Compute a composite legend grouping column from selected tag columns.

    Returns the column name to use as *group_col*, or ``None`` when no
    tag columns are available.
    """
    legend_by = legend_by or [TAG_SERIES]
    cols = [c for c in legend_by if c in df.columns]
    if not cols:
        return None
    if len(cols) == 1:
        return cols[0]
    col_name = "_legend_key"
    parts = [df[c].astype(str) for c in cols]
    df[col_name] = parts[0].str.cat(parts[1:], sep=" | ")
    return col_name


def _effective_legend_by(legend_by, facet_by, tag_filters, selected_series=None):
    """Compute effective legend columns from explicit selection + context.

    Rules for phase 1:
    - Preserve user-selected order.
    - If nothing is selected, derive contextual defaults.
    - Facet dimension is excluded from legend.
    """
    selected = list(legend_by or [])
    out = []
    parents = _as_parent_list(selected_series)
    multi_parent = len(set(parents)) > 1

    # Preserve selected order first.
    for col in selected:
        if col and col != facet_by and col not in out:
            out.append(col)

    # Context defaults only when user did not explicitly select legend columns.
    if not selected:
        if multi_parent and facet_by != TAG_SERIES:
            out.append(TAG_SERIES)
        if isinstance(tag_filters, dict):
            for col, vals in tag_filters.items():
                if vals and col != facet_by and col not in out:
                    out.append(col)

    return out


def _build_faceted_figure(df, x_col, y1_cols, y2_cols, data_manager,
                          group_col, facet_col, facet_order=None):
    """Small-multiples layout: one subplot per unique value of *facet_col*."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from ..visualization import rgb_to_rgba

    y1_cols = list(y1_cols) if y1_cols else []
    y2_cols = list(y2_cols) if y2_cols else []
    has_y2 = bool(y2_cols)

    if x_col == "Elapsed time" and "Elapsed time" in df.columns:
        df = df.copy()
        df["Elapsed time"] = df["Elapsed time"] / 3600.0
        for suffix in ("_min", "_max", "_mean"):
            agg_col = f"Elapsed time{suffix}"
            if agg_col in df.columns:
                df[agg_col] = df[agg_col] / 3600.0

    facet_values = list(df[facet_col].dropna().unique())
    if facet_order:
        ordered = [v for v in facet_order if v in facet_values]
        facet_values = ordered + [v for v in facet_values if v not in ordered]
    n_facets = len(facet_values)
    if n_facets == 0:
        return empty_figure("No facet groups found")

    n_cols = min(n_facets, 3)
    n_rows = (n_facets + n_cols - 1) // n_cols

    specs = [[{"secondary_y": has_y2} for _ in range(n_cols)]
             for _ in range(n_rows)]
    fig = make_subplots(
        rows=n_rows, cols=n_cols,
        subplot_titles=[str(v) for v in facet_values],
        specs=specs,
        shared_yaxes=True,
        horizontal_spacing=0.05,
        vertical_spacing=0.10,
    )

    is_time_x = (x_col == "Elapsed time")
    scatter_mode = "lines" if is_time_x else "markers"
    agg_keywords = ["min", "max", "mean"]
    has_agg = any(
        c.lower().endswith(kw) for c in df.columns for kw in agg_keywords
    )
    use_bands = has_agg and is_time_x

    eff_x = x_col
    if not is_time_x:
        mean_x = add_agg_suffix(x_col, "mean")
        if mean_x in df.columns:
            eff_x = mean_x

    eff_y1 = y1_cols
    eff_y2 = y2_cols
    if has_agg and not is_time_x:
        eff_y1 = [add_agg_suffix(b, "mean") if add_agg_suffix(b, "mean") in df.columns else b for b in y1_cols]
        eff_y2 = [add_agg_suffix(b, "mean") if add_agg_suffix(b, "mean") in df.columns else b for b in y2_cols]

    _n_vars = len(y1_cols) + len(y2_cols)

    for idx, facet_val in enumerate(facet_values):
        r = idx // n_cols + 1
        c = idx % n_cols + 1
        sub = df[df[facet_col] == facet_val]

        do_group = (group_col and group_col in sub.columns
                    and group_col != facet_col)

        if do_group:
            groups = sorted(sub[group_col].unique())
            offset = 0
            for g in groups:
                gsub = sub[sub[group_col] == g]
                pfx = str(g)
                if use_bands:
                    add_band_traces(fig, gsub, eff_x, y1_cols, y2_cols,
                                    scatter_mode, color_offset=offset,
                                    name_prefix=pfx,
                                    subplot_row=r, subplot_col=c)
                else:
                    add_standard_traces(fig, gsub, eff_x, eff_y1, eff_y2,
                                        scatter_mode, color_offset=offset,
                                        name_prefix=pfx,
                                        subplot_row=r, subplot_col=c)
                offset += _n_vars
        else:
            if use_bands:
                add_band_traces(fig, sub, eff_x, y1_cols, y2_cols,
                                scatter_mode,
                                subplot_row=r, subplot_col=c)
            else:
                add_standard_traces(fig, sub, eff_x, eff_y1, eff_y2,
                                    scatter_mode,
                                    subplot_row=r, subplot_col=c)

    # De-duplicate legend entries
    seen_names = set()
    for trace in fig.data:
        if trace.name in seen_names:
            trace.showlegend = False
        elif trace.showlegend is not False:
            seen_names.add(trace.name)

    units = data_manager.units or {}
    x_label = "Elapsed time [h]" if is_time_x else x_col
    for cc in range(1, n_cols + 1):
        fig.update_xaxes(title_text=x_label, row=n_rows, col=cc)

    fig.update_layout(
        height=max(400, 350 * n_rows),
        margin=dict(l=60, r=40, t=40, b=10),
        legend=dict(orientation="v", yanchor="top", y=1,
                    xanchor="left", x=1.02, font=dict(size=10)),
    )

    return fig


def _build_figure(df, x_col, y1_cols, y2_cols, data_manager,
                  group_col=None, facet_col=None, facet_order=None):
    """Build a Plotly figure for the custom report.

    When *group_col* is given, traces are split by unique values in that
    column with distinct colour offsets.  When *facet_col* is given, data
    is split into small-multiple subplots.
    """
    if facet_col:
        return _build_faceted_figure(df, x_col, y1_cols, y2_cols,
                                     data_manager, group_col, facet_col,
                                     facet_order=facet_order)

    fig = plot_report(
        df,
        x_col=x_col,
        y1_cols=y1_cols if y1_cols else None,
        y2_cols=y2_cols if y2_cols else None,
        labels={},
        units=data_manager.units,
        open_in_browser=False,
        group_col=group_col,
    )

    return finalise_figure(fig)

