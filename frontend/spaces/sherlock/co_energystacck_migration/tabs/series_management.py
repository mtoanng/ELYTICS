"""series_management -- Dash tab for series definition and mapping management.

Provides ``layout()`` which returns the tab's component tree and
``register_callbacks(app, data_manager)`` which wires up all interactivity.

Replaces the Tkinter "Data Onboarding" tab, merging the two sub-tabs
(Series Definitions + Mapping) into a single side-by-side layout:

  Left column (~45 %)  â€“ series selector, dynamic form, action buttons
  Right column (~55 %) â€“ mapping DataTable with inline editing

Key features
------------
* Cascading dropdowns: series â†’ files â†’ worksheets â†’ header rows.
* ``dcc.Upload`` for adding Excel files to the bronze layer.
* ``dash_table.DataTable`` with per-column dropdowns for mapping editing.
* Conditional row styling (red = unmapped file column, green = mapped).
* Modals for New / Delete / Detect Rows / Delete Aggregation dialogs.
* All operations delegate to existing ``SeriesDataManager`` methods â€“
  no backend changes required.

Persistence model
-----------------
* Draft mode is staged in memory first and committed explicitly via Save.
* For existing saved series, disruptive edits are also staged in memory and
    only written to ``series.json`` on Save.
* Cleanup of detached/orphaned source files remains a separate explicit step.
"""

import base64
import io
import json
import logging
import os
import tempfile

import dash_bootstrap_components as dbc
import pandas as pd
from dash import dash_table, dcc, html, no_update, callback_context
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate

from ..backend.series_data_manager import SeriesDataManager
from ..backend.data_loading import detect_header_and_data_row
from ..backend.tag_manager import TagManager

logger = logging.getLogger(__name__)

# â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _series_options(dm: SeriesDataManager):
    """Build dropdown options from current series definitions."""
    return [{"label": k, "value": k} for k in dm.series_defs.keys()]


def _stack_type_options(dm: SeriesDataManager):
    """Build dropdown options from available stack type definitions."""
    return [{"label": k, "value": k} for k in dm.stack_definitions.keys()]


def _file_options(dm: SeriesDataManager, series_name):
    """Build dropdown options for files attached to *series_name*."""
    sdef = dm.series_defs.get(series_name, {})
    return [
        {"label": f.get("path", f"File {i+1}"), "value": i}
        for i, f in enumerate(sdef.get("files", []))
    ]


def _ws_options(dm: SeriesDataManager, series_name, file_idx):
    """Build dropdown options for worksheets in the selected file."""
    sdef = dm.series_defs.get(series_name, {})
    files = sdef.get("files", [])
    if file_idx is None or file_idx < 0 or file_idx >= len(files):
        return []
    wss = files[file_idx].get("worksheets", [])
    return [
        {"label": ws.get("name", f"Worksheet {j+1}"), "value": j}
        for j, ws in enumerate(wss)
    ]


def _header_vals(dm: SeriesDataManager, series_name, file_idx, ws_idx):
    """Return (header_row, first_data_row) strings for the selected worksheet."""
    sdef = dm.series_defs.get(series_name, {})
    files = sdef.get("files", [])
    if (file_idx is None or ws_idx is None
            or file_idx < 0 or file_idx >= len(files)):
        return "", ""
    wss = files[file_idx].get("worksheets", [])
    if ws_idx < 0 or ws_idx >= len(wss):
        return "", ""
    ws = wss[ws_idx]
    return str(ws.get("header_row", "")), str(ws.get("first_data_row", ""))


def _agg_display(dm, series_name):
    """Return a human-readable summary of registered aggregation intervals."""
    agg_list = dm.series_defs.get(series_name, {}).get("aggregations", [])
    return ", ".join(f"{v} min" for v in agg_list) if agg_list else "(none)"


def _row_style(row):
    """Return a CSS style dict for conditional mapping-table row colouring."""
    origin = row.get("origin", "")
    file_col = row.get("file_column", "")
    if origin == "file" and not file_col:
        return {"backgroundColor": "#ffcccc"}      # red â€“ unmapped
    elif origin == "file" and file_col:
        return {"backgroundColor": "#ccffcc"}      # green â€“ mapped
    return {}


# â”€â”€ layout â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def layout(data_manager: SeriesDataManager, tag_manager=None):
    """Return the Dash component tree for the Series Management tab."""

    series_opts = _series_options(data_manager)
    stack_opts = _stack_type_options(data_manager)

    first_series = list(data_manager.series_defs.keys())[0] if data_manager.series_defs else None

    # --- left column (series definition) ---
    left_col = dbc.Col(
        width=5,
        style={"overflowY": "auto", "maxHeight": "100%", "paddingRight": "12px"},
        children=[
            # Series selector
            dbc.Row([
                dbc.Col([
                    dbc.Label("Series", className="fw-bold small mb-0"),
                    dcc.Dropdown(
                        id="sm-series-dropdown",
                        options=series_opts,
                        value=first_series,
                        clearable=False,
                        style={"fontSize": "0.85rem"},
                    ),
                ], width=6),
                dbc.Col([
                    dbc.Label("\u00a0", className="small mb-0"),  # spacer
                    dbc.Button("New", id="sm-btn-new", color="primary",
                               size="sm", className="w-100"),
                ], width=2),
                dbc.Col([
                    dbc.Label("\u00a0", className="small mb-0"),
                    dbc.Button("Delete", id="sm-btn-delete", color="danger",
                               size="sm", className="w-100"),
                ], width=2),
                dbc.Col([
                    dbc.Label("\u00a0", className="small mb-0"),
                    dbc.Button("Cleanup", id="sm-btn-cleanup", color="dark",
                               size="sm", className="w-100"),
                ], width=2),
            ], className="mb-2"),

            # â”€â”€ top-level fields â”€â”€
            dbc.Row([
                dbc.Col(dbc.Label("name", className="small mb-0 text-end"),
                        width=3, className="d-flex align-items-center justify-content-end"),
                dbc.Col(dbc.Input(id="sm-field-name", size="sm"), width=9),
            ], className="mb-1"),
            dbc.Row([
                dbc.Col(dbc.Label("stack_type", className="small mb-0 text-end"),
                        width=3, className="d-flex align-items-center justify-content-end"),
                dbc.Col(dcc.Dropdown(
                    id="sm-stack-type",
                    options=stack_opts,
                    clearable=True,
                    style={"fontSize": "0.85rem"},
                ), width=9),
            ], className="mb-1"),
            dbc.Row([
                dbc.Col(dbc.Label("mapping", className="small mb-0 text-end"),
                        width=3, className="d-flex align-items-center justify-content-end"),
                dbc.Col(dbc.Input(id="sm-field-mapping", size="sm",
                                  disabled=True), width=9),
            ], className="mb-1"),

            # â”€â”€ files â”€â”€
            dbc.Row([
                dbc.Col(dbc.Label("file(s)", className="small mb-0 text-end"),
                        width=3, className="d-flex align-items-start justify-content-end pt-1"),
                dbc.Col(dcc.Dropdown(
                    id="sm-file-dropdown",
                    clearable=False,
                    style={"fontSize": "0.85rem"},
                ), width=6),
                dbc.Col([
                    dcc.Upload(
                        id="sm-file-upload",
                        children=dbc.Button("Add", id="sm-btn-add-file", color="secondary",
                                            size="sm", className="w-100"),
                        accept=".xlsx",
                    ),
                    dbc.Button("Remove", id="sm-btn-del-file", color="secondary",
                               size="sm", className="w-100 mt-1"),
                ], width=3),
            ], className="mb-1"),

            # â”€â”€ worksheets â”€â”€
            dbc.Row([
                dbc.Col(dbc.Label("worksheet", className="small mb-0 text-end"),
                        width=3, className="d-flex align-items-center justify-content-end"),
                dbc.Col(dcc.Dropdown(
                    id="sm-ws-dropdown",
                    clearable=False,
                    style={"fontSize": "0.85rem"},
                ), width=9),
            ], className="mb-1"),

            # â”€â”€ header / first-data row â”€â”€
            dbc.Row([
                dbc.Col(dbc.Label("header row", className="small mb-0 text-end"),
                        width=3, className="d-flex align-items-center justify-content-end"),
                dbc.Col(dbc.Input(id="sm-header-row", type="number",
                                  size="sm"), width=3),
                dbc.Col(dbc.Label("first data row", className="small mb-0 text-end"),
                        width=3, className="d-flex align-items-center justify-content-end"),
                dbc.Col(dbc.Input(id="sm-first-data-row", type="number",
                                  size="sm"), width=3),
            ], className="mb-1"),
            dbc.Row([
                dbc.Col(width=3),
                dbc.Col(dbc.Button("Detect headers", id="sm-btn-detect",
                                   color="info", size="sm"), width=3),
            ], className="mb-2"),

            html.Hr(className="my-1"),
            html.Small("Optional Parameters", className="fw-bold"),

            # â”€â”€ options (time_offset [h]) â”€â”€
            dbc.Row([
                dbc.Col(dbc.Label("time_offset [h]", className="small mb-0 text-end"),
                        width=3, className="d-flex align-items-center justify-content-end"),
                dbc.Col(dbc.Input(id="sm-opt-time-offset", size="sm"),
                        width=9),
            ], className="mb-1"),

            # â”€â”€ aggregations display â”€â”€
            dbc.Row([
                dbc.Col(dbc.Label("aggregations", className="small mb-0 text-end"),
                        width=3, className="d-flex align-items-center justify-content-end"),
                dbc.Col(html.Span(id="sm-agg-display", children="(none)",
                                  className="small"), width=6),
                dbc.Col(dbc.Button("Delete Aggregation", id="sm-btn-del-agg",
                                   color="secondary", size="sm",
                                   className="w-100"), width=3),
            ], className="mb-2"),

            # â”€â”€ tag summary â”€â”€
            html.Small("Tag Summary", className="fw-bold"),
            html.Div(id="sm-tag-summary",
                     children="(no tags)",
                     className="small text-muted mb-1"),

            html.Hr(className="my-1"),

            # â”€â”€ action button row â”€â”€
            dbc.Row([
                dbc.Col(dbc.Button("Save", id="sm-btn-save",
                                   color="success", size="sm",
                                   className="w-100"), width=2),
                dbc.Col(dbc.Button("Materialize", id="sm-btn-materialize",
                                   color="warning", size="sm",
                                   className="w-100"), width=3),
                dbc.Col(dbc.Button("Aggregate", id="sm-btn-aggregate",
                                   color="info", size="sm",
                                   className="w-100"), width=3),
                dbc.Col(dbc.Input(id="sm-agg-interval", value="15",
                                  size="sm", type="number",
                                  style={"width": "80px"}), width=2),
                dbc.Col(html.Span("min", className="small pt-1"), width=1),
            ], className="mb-2"),

            html.Div(
                id="sm-workflow-helper",
                className="small text-muted mb-2 px-2 py-1",
                style={
                    "display": "none",
                    "border": "1px solid #dbeafe",
                    "borderRadius": "4px",
                    "backgroundColor": "#f8fbff",
                },
                children="",
            ),

            # â”€â”€ status alert â”€â”€
            dcc.Loading(
                id="sm-loading-materialize",
                type="circle",
                children=[
                    dbc.Alert(
                        id="sm-status-alert",
                        is_open=False,
                        duration=6000,
                        dismissable=True,
                        className="mb-0 py-1 small"
                    )
                ]
            )
        ],
    )

    # --- right column (mapping + tag manager subtabs) ---
    mapping_content = html.Div(
        children=[
            # mapping header row (buttons always visible at top)
            dbc.Row([
                dbc.Col(dbc.Button("Show Mapping", id="sm-btn-show-map",
                                   color="primary", size="sm"), width="auto"),
                dbc.Col(dbc.Button("Save Mapping", id="sm-btn-save-map",
                                   color="success", size="sm"), width="auto",
                        className="ms-2"),
                dbc.Col(dbc.Button("Delete Mapping", id="sm-btn-del-map",
                                   color="danger", size="sm"), width="auto",
                        className="ms-1"),
                dbc.Col([
                    html.Span("Unmapped file columns: ",
                              className="small fw-bold"),
                    html.Span(id="sm-unmapped-badge",
                              className="badge bg-secondary"),
                ], width="auto", className="d-flex align-items-center ms-3"),
            ], className="mb-2"),

            # mapping DataTable (scrollable)
            dash_table.DataTable(
                id="sm-mapping-table",
                columns=[
                    {"name": "schema_column", "id": "schema_column",
                     "presentation": "dropdown", "editable": True},
                    {"name": "file_column", "id": "file_column",
                     "presentation": "dropdown", "editable": True},
                    {"name": "example", "id": "example",
                     "editable": False},
                    {"name": "origin", "id": "origin",
                     "editable": False},
                ],
                data=[],
                editable=True,
                row_deletable=False,
                style_table={"overflowX": "auto",
                             "overflowY": "auto",
                             "maxHeight": "calc(100vh - 220px)"},
                style_cell={"fontSize": "0.82rem",
                            "padding": "4px 8px",
                            "textAlign": "left",
                            "minWidth": "100px"},
                style_header={"fontWeight": "bold",
                              "backgroundColor": "#f0f0f0"},
                style_data_conditional=[],
                dropdown={},
                dropdown_conditional=[],
                fixed_rows={"headers": True},
            ),
        ],
    )

    # â”€â”€ build initial tag-definitions table rows â”€â”€
    _tag_def_rows = []
    if tag_manager is not None:
        for d in tag_manager.get_tag_definitions():
            _tag_def_rows.append({
                "id": d["id"],
                "label": d["label"],
                "source": d["source"],
                "unit_divisor": d.get("unit_divisor", 1),
                "default_category": d.get("default_category", "uncategorized"),
                "categories": ", ".join(d.get("categories", [])),
            })

    _tag_label_opts = []
    if tag_manager is not None:
        _tag_label_opts = [
            {"label": d["label"], "value": d["id"]}
            for d in tag_manager.get_tag_definitions()
        ]

    # Read schema column names for the source dropdown
    _schema_source_opts = []
    _schema_path = os.path.join(
        data_manager._get_project_root(), "config", "schema.csv")
    if os.path.isfile(_schema_path):
        _schema_df = pd.read_csv(_schema_path)
        _schema_source_opts = sorted(_schema_df["name"].dropna().tolist())

    tag_mgr_content = html.Div(
        style={"padding": "8px"},
        children=[
            # â”€â”€ Section 1: Tag Definitions â”€â”€
            html.Small("Tag Definitions", className="fw-bold"),

            dash_table.DataTable(
                id="tm-def-table",
                columns=[
                    {"name": "id", "id": "id", "editable": False,
                     "type": "numeric"},
                    {"name": "label", "id": "label", "editable": True},
                    {"name": "source", "id": "source",
                     "editable": False},
                    {"name": "divisor", "id": "unit_divisor",
                     "editable": True, "type": "numeric"},
                    {"name": "default_category", "id": "default_category",
                     "editable": True},
                    {"name": "categories", "id": "categories",
                     "editable": True},
                ],
                data=_tag_def_rows,
                editable=True,
                row_deletable=False,
                row_selectable="single",
                style_table={"overflowX": "auto"},
                style_cell={"fontSize": "0.82rem",
                            "padding": "4px 8px",
                            "textAlign": "left",
                            "minWidth": "80px"},
                style_header={"fontWeight": "bold",
                              "backgroundColor": "#f0f0f0"},
                style_cell_conditional=[
                    {"if": {"column_id": "id"},
                     "width": "40px", "minWidth": "40px",
                     "maxWidth": "50px"},
                    {"if": {"column_id": "unit_divisor"},
                     "width": "70px", "minWidth": "60px",
                     "maxWidth": "80px"},
                    {"if": {"column_id": "source"},
                     "backgroundColor": "#f8f8f8"},
                ],
            ),

            # Source selector (standalone dropdown, updates selected row)
            dbc.Row([
                dbc.Col(dbc.Label("Source for selected row:",
                                  className="small mb-0"),
                        width="auto",
                        className="d-flex align-items-center"),
                dbc.Col(dcc.Dropdown(
                    id="tm-source-dropdown",
                    options=[{"label": s, "value": s}
                             for s in _schema_source_opts],
                    placeholder="Select a schema column\u2026",
                    clearable=True,
                    style={"fontSize": "0.85rem"},
                ), width=5),
            ], id="tm-source-row", className="mt-1 mb-1",
               style={"display": "none"}),

            dbc.Row([
                dbc.Col(dbc.Button("Add Tag", id="tm-btn-add-def",
                                   color="primary", size="sm"),
                        width="auto"),
                dbc.Col(dbc.Button("Remove Selected Tag",
                                   id="tm-btn-remove-def",
                                   color="danger", size="sm"),
                        width="auto", className="ms-2"),
                dbc.Col(dbc.Button("Save Tags", id="tm-btn-save-defs",
                                   color="success", size="sm"),
                        width="auto", className="ms-2"),
                dbc.Col(html.Span(id="tm-def-status",
                                  className="small text-muted"),
                        width="auto",
                        className="d-flex align-items-center ms-2"),
            ], className="mt-2 mb-3"),

            html.Hr(className="my-2"),

            # â”€â”€ Section 2: Series Ranges â”€â”€
            html.Small("Series Ranges", className="fw-bold"),

            dbc.Row([
                dbc.Col(dbc.Label("Tag", className="small mb-0 text-end"),
                        width=2,
                        className="d-flex align-items-center justify-content-end"),
                dbc.Col(dcc.Dropdown(
                    id="tm-tag-dropdown",
                    options=_tag_label_opts,
                    value=_tag_label_opts[0]["value"] if _tag_label_opts else None,
                    clearable=False,
                    style={"fontSize": "0.85rem"},
                ), width=6),
                dbc.Col(html.Span(id="tm-series-label",
                                  className="small fw-bold text-primary"),
                        width=4,
                        className="d-flex align-items-center"),
            ], className="mt-2 mb-2"),

            dash_table.DataTable(
                id="tm-range-table",
                columns=[
                    {"name": "category", "id": "category",
                     "editable": False},
                    {"name": "ranges", "id": "ranges",
                     "editable": True},
                ],
                data=[],
                editable=True,
                row_deletable=False,
                style_table={"overflowX": "auto"},
                style_cell={"fontSize": "0.82rem",
                            "padding": "4px 8px",
                            "textAlign": "left",
                            "minWidth": "100px"},
                style_header={"fontWeight": "bold",
                              "backgroundColor": "#f0f0f0"},
                style_cell_conditional=[
                    {"if": {"column_id": "category"},
                     "width": "140px", "minWidth": "100px",
                     "maxWidth": "180px",
                     "backgroundColor": "#fafafa"},
                ],
                fixed_rows={"headers": True},
            ),

            html.Hr(className="my-2"),

            # â”€â”€ Save Ranges button â”€â”€
            dbc.Row([
                dbc.Col(dbc.Button("Save Ranges", id="tm-btn-save-ranges",
                                   color="success", size="sm"),
                        width="auto"),
                dbc.Col(html.Span(id="tm-save-status",
                                  className="small text-muted"),
                        width="auto",
                        className="d-flex align-items-center ms-2"),
            ]),
        ],
    )

    right_col = dbc.Col(
        width=7,
        style={"overflowY": "auto", "overflowX": "auto",
               "maxHeight": "100%"},
        children=[
            dbc.Tabs(
                id="sm-right-tabs",
                active_tab="sm-tab-mapping",
                className="nav-tabs-custom",
                children=[
                    dbc.Tab(mapping_content,
                            label="Mapping",
                            tab_id="sm-tab-mapping",
                            label_class_name="text-dark"),
                    dbc.Tab(tag_mgr_content,
                            label="Tag Manager",
                            tab_id="sm-tab-tags",
                            label_class_name="text-dark"),
                ],
            ),
        ],
    )

    # --- modals ---
    modal_new = dbc.Modal([
        dbc.ModalHeader("New Series"),
        dbc.ModalBody(dbc.Input(id="sm-new-name-input", placeholder="Series name")),
        dbc.ModalFooter([
            dbc.Button("Create", id="sm-new-confirm", color="primary", size="sm"),
            dbc.Button("Cancel", id="sm-new-cancel", className="ms-2", size="sm"),
        ]),
    ], id="sm-modal-new", is_open=False)

    modal_delete = dbc.Modal([
        dbc.ModalHeader("Delete Series"),
        dbc.ModalBody(id="sm-delete-body"),
        dbc.ModalFooter([
            dbc.Button("Next: detach only", id="sm-del-keep",
                        color="warning", size="sm"),
            dbc.Button("Next: detach + delete artifacts", id="sm-del-files",
                        color="danger", size="sm", className="ms-2"),
            dbc.Button("Cancel", id="sm-del-cancel", className="ms-2",
                        size="sm"),
        ]),
    ], id="sm-modal-delete", is_open=False)

    modal_delete_confirm = dbc.Modal([
        dbc.ModalHeader("Confirm Deletion"),
        dbc.ModalBody(id="sm-delete-confirm-body"),
        dbc.ModalFooter([
            dbc.Button("Delete", id="sm-del-final-confirm", color="danger",
                       size="sm"),
            dbc.Button("Back", id="sm-del-final-cancel", className="ms-2",
                       size="sm"),
        ]),
    ], id="sm-modal-delete-confirm", is_open=False)

    modal_unsaved_draft = dbc.Modal([
        dbc.ModalHeader("Unsaved Draft"),
        dbc.ModalBody(
            "You have an unsaved draft series. Switch series and discard the draft changes?"
        ),
        dbc.ModalFooter([
            dbc.Button("Discard and switch", id="sm-draft-discard-continue",
                       color="warning", size="sm"),
            dbc.Button("Stay", id="sm-draft-discard-cancel", className="ms-2",
                       size="sm"),
        ]),
    ], id="sm-modal-unsaved-draft", is_open=False)

    modal_overwrite = dbc.Modal([
        dbc.ModalHeader("File already exists"),
        dbc.ModalBody(id="sm-overwrite-body",
                      children="A file with this name already exists in bronze."),
        dbc.ModalFooter([
            dbc.Button("Attach existing", id="sm-overwrite-attach", color="success",
                        size="sm"),
            dbc.Button("Overwrite", id="sm-overwrite-yes", color="danger",
                        size="sm", className="ms-2"),
            dbc.Button("Cancel", id="sm-overwrite-no", className="ms-2",
                        size="sm"),
        ]),
    ], id="sm-modal-overwrite", is_open=False)

    modal_detect = dbc.Modal([
        dbc.ModalHeader("Manual Header / Data Row Selection"),
        dbc.ModalBody([
            html.P("Auto-detection failed. Please review the preview and enter row indices."),
            dash_table.DataTable(id="sm-detect-preview",
                                 style_cell={"fontSize": "0.8rem",
                                             "padding": "2px 6px"}),
            dbc.Row([
                dbc.Col([dbc.Label("Header row (0-based)", className="small"),
                         dbc.Input(id="sm-detect-header", type="number",
                                   size="sm")], width=6),
                dbc.Col([dbc.Label("First data row (0-based)", className="small"),
                         dbc.Input(id="sm-detect-data", type="number",
                                   size="sm")], width=6),
            ], className="mt-2"),
        ]),
        dbc.ModalFooter([
            dbc.Button("Apply", id="sm-detect-apply", color="primary",
                        size="sm"),
            dbc.Button("Cancel", id="sm-detect-cancel", className="ms-2",
                        size="sm"),
        ]),
    ], id="sm-modal-detect", is_open=False)

    modal_del_agg = dbc.Modal([
        dbc.ModalHeader("Delete Aggregation"),
        dbc.ModalBody([
            html.P(id="sm-delagg-text"),
            dbc.RadioItems(id="sm-delagg-radio", inline=True),
        ]),
        dbc.ModalFooter([
            dbc.Button("Delete", id="sm-delagg-confirm", color="danger",
                        size="sm"),
            dbc.Button("Cancel", id="sm-delagg-cancel", className="ms-2",
                        size="sm"),
        ]),
    ], id="sm-modal-delagg", is_open=False)

    modal_del_map = dbc.Modal([
        dbc.ModalHeader("Detach Mapping"),
        dbc.ModalBody(id="sm-del-map-body"),
        dbc.ModalFooter([
            dbc.Button("Detach", id="sm-del-map-confirm", color="warning", size="sm"),
            dbc.Button("Cancel", id="sm-del-map-cancel", className="ms-2", size="sm"),
        ]),
    ], id="sm-modal-del-map", is_open=False)

    modal_cleanup = dbc.Modal([
        dbc.ModalHeader("Cleanup Orphaned Files"),
        dbc.ModalBody([
            html.P("The following orphaned files were found (not associated with any series):"),
            dash_table.DataTable(
                id="sm-cleanup-table",
                columns=[
                    {"name": "File Name", "id": "rel_path"},
                    {"name": "Size (KB)", "id": "size_kb"},
                    {"name": "Creation Datetime", "id": "created_dt"},
                ],
                data=[],
                style_cell={"fontSize": "0.8rem", "padding": "4px 6px"},
                style_table={"maxHeight": "400px", "overflowY": "auto"},
            ),
        ]),
        dbc.ModalFooter([
            dbc.Button("Delete All", id="sm-cleanup-confirm", color="danger",
                        size="sm"),
            dbc.Button("Cancel", id="sm-cleanup-cancel", className="ms-2",
                        size="sm"),
        ]),
    ], id="sm-modal-cleanup", is_open=False, style={"width": "900px", "maxWidth": "90vw"})

    # --- hidden stores ---
    stores = [
        dcc.Store(id="sm-store-upload-temp", storage_type="memory"),
        dcc.Store(id="sm-store-detect-preview-df", storage_type="memory"),
        dcc.Store(id="sm-store-mapping-schema-names", storage_type="memory"),
        dcc.Store(id="sm-store-mapping-file-cols", storage_type="memory"),
        dcc.Store(id="sm-store-draft-series", storage_type="memory"),
        dcc.Store(id="sm-store-delete-mode", storage_type="memory"),
        dcc.Store(id="sm-store-pending-series", storage_type="memory"),
        dcc.Store(id="sm-store-last-series", storage_type="memory", data=first_series),
        dcc.Store(id="sm-store-cleanup-refresh", storage_type="memory", data=0),
        dcc.Store(id="sm-store-mapping-detach-tick", storage_type="memory", data=0),
        dcc.Store(id="tm-store-def-dirty", storage_type="memory", data=False),
        dcc.Store(id="tm-store-ranges-dirty", storage_type="memory", data=False),
    ]

    return html.Div(
        style={"flex": "1 1 auto", "display": "flex", "flexDirection": "column",
               "overflow": "hidden", "minHeight": "0"},
        children=[
            *stores,
            modal_new, modal_delete, modal_delete_confirm, modal_unsaved_draft,
            modal_overwrite, modal_detect, modal_del_agg, modal_del_map, modal_cleanup,
            dbc.Card(
                dbc.CardBody(
                    dbc.Row([left_col, right_col],
                            style={"height": "100%"}),
                    style={"height": "100%", "overflow": "hidden",
                           "padding": "8px 12px"},
                ),
                className="mx-2 mt-2",
                style={"flex": "1 1 auto", "overflow": "hidden"},
            ),
        ],
    )


# â”€â”€ callbacks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def register_callbacks(app, data_manager: SeriesDataManager, tag_manager=None):
    """Wire up all interactivity for the Series Management tab."""

    @app.callback(
        [
            Output("sm-series-dropdown", "disabled"),
            Output("sm-btn-delete", "disabled"),
            Output("sm-btn-materialize", "disabled"),
            Output("sm-btn-aggregate", "disabled"),
            Output("sm-btn-del-agg", "disabled"),
            Output("sm-btn-del-file", "disabled"),
            Output("sm-btn-del-map", "disabled"),
            Output("sm-btn-new", "color"),
            Output("sm-btn-add-file", "color"),
            Output("sm-btn-show-map", "color"),
            Output("sm-btn-save-map", "color"),
            Output("sm-btn-save", "color"),
            Output("sm-btn-save", "disabled"),
            Output("sm-btn-materialize", "color"),
            Output("sm-btn-aggregate", "color"),
            Output("sm-btn-del-file", "color"),
            Output("sm-btn-del-agg", "color"),
            Output("sm-btn-del-map", "color"),
            Output("sm-btn-detect", "color"),
            Output("sm-stack-type", "style"),
            Output("sm-workflow-helper", "children"),
            Output("sm-workflow-helper", "style"),
        ],
        [
            Input("sm-store-draft-series", "data"),
            Input("sm-series-dropdown", "value"),
            Input("sm-field-name", "value"),
            Input("sm-stack-type", "value"),
            Input("sm-field-mapping", "value"),
            Input("sm-opt-time-offset", "value"),
            Input("sm-file-dropdown", "options"),
            Input("sm-mapping-table", "data"),
            Input("sm-agg-display", "children"),
            Input("store-series-refresh", "data"),
            Input("sm-store-mapping-detach-tick", "data"),
        ],
        prevent_initial_call=False,
    )
    def set_saved_series_controls_state(draft_series_name, selected_series,
                                        name_val, stack_type_val,
                                        mapping_val, offset_val,
                                        _file_opts, mapping_table_data, _agg_disp,
                                        _refresh_tick, _detach_tick):
        in_draft_mode = bool(draft_series_name)
        target_series = draft_series_name or selected_series

        # Semantic palette: green=next step, blue=available, gray=disabled, red=destructive.
        green = "success"
        blue = "primary"
        gray = "secondary"
        red = "danger"

        base_stack_style = {"fontSize": "0.85rem"}
        stack_style = dict(base_stack_style)

        sdef = data_manager.series_defs.get(target_series, {}) if target_series else {}
        files = sdef.get("files", [])
        has_name = bool((name_val or "").strip())
        has_stack = bool((stack_type_val or "").strip())
        has_files = len(files) > 0
        has_mapping = bool((mapping_val or "").strip())
        headers_ok = True
        if has_files:
            for fentry in files:
                wss = fentry.get("worksheets", [])
                if not wss:
                    headers_ok = False
                    break
                for ws in wss:
                    if ws.get("header_row") is None or ws.get("first_data_row") is None:
                        headers_ok = False
                        break
                if not headers_ok:
                    break

        # Draft commits stay strict; existing-series edits are allowed to be staged
        # and saved even when not materialization-ready yet.
        can_save_draft = has_name and has_stack and has_files and has_mapping and headers_ok
        can_save_existing = has_name and has_stack

        saved_name = str(sdef.get("name", ""))
        saved_stack = str(sdef.get("stack_type", "") or "")
        saved_mapping = str(sdef.get("mapping", "") or "")
        saved_offset = str(sdef.get("options", {}).get("time_offset [h]", "") or "")
        current_offset = str(offset_val or "")
        dirty_basic = (
            str(name_val or "") != saved_name
            or str(stack_type_val or "") != saved_stack
            or str(mapping_val or "") != saved_mapping
            or current_offset != saved_offset
        )

        # For saved series, treat any uncommitted delta vs disk as dirty.
        dirty_disk_diff = False
        dirty_form_vs_disk = False
        if (not in_draft_mode) and selected_series:
            try:
                disk_defs = data_manager._load_series_defs()
                mem_def = data_manager.series_defs.get(selected_series, {})
                disk_def = disk_defs.get(selected_series, {})
                dirty_disk_diff = json.dumps(mem_def, sort_keys=True) != json.dumps(disk_def, sort_keys=True)

                # Also compare current form fields to the persisted record.
                disk_name = str(disk_def.get("name", ""))
                disk_stack = str(disk_def.get("stack_type", "") or "")
                disk_mapping = str(disk_def.get("mapping", "") or "")
                disk_offset = str(disk_def.get("options", {}).get("time_offset [h]", "") or "")
                dirty_form_vs_disk = (
                    str(name_val or "") != disk_name
                    or str(stack_type_val or "") != disk_stack
                    or str(mapping_val or "") != disk_mapping
                    or current_offset != disk_offset
                )
            except Exception:
                dirty_disk_diff = False
                dirty_form_vs_disk = False
        
        # Detach tick is a UI nudge only; persistent dirty state must come from
        # actual form/disk deltas so Save can clear it deterministically.
        dirty_detach = False

        # Defaults
        series_disabled = False
        delete_disabled = in_draft_mode
        has_silver = bool(selected_series) and os.path.exists(data_manager._get_silver_path(selected_series))
        agg_count = len(data_manager.series_defs.get(selected_series, {}).get("aggregations", [])) if selected_series else 0
        can_materialize = bool(selected_series) and has_name and has_stack and has_files and has_mapping and headers_ok
        materialize_disabled = in_draft_mode or (not can_materialize)
        aggregate_disabled = in_draft_mode or (not has_silver)
        delagg_disabled = in_draft_mode or agg_count == 0
        del_file_disabled = not has_files
        del_map_disabled = not has_mapping

        btn_new_color = blue
        btn_add_color = blue
        btn_show_map_color = blue
        btn_save_map_color = blue
        btn_save_color = blue
        btn_materialize_color = blue
        btn_aggregate_color = blue
        btn_del_file_color = red if not del_file_disabled else gray
        btn_del_agg_color = red if not delagg_disabled else gray
        btn_del_map_color = red if not del_map_disabled else gray
        btn_detect_color = blue if has_files else gray

        dirty = bool(dirty_basic or dirty_disk_diff or dirty_form_vs_disk or dirty_detach)
        if in_draft_mode:
            save_disabled = not can_save_draft
        else:
            save_disabled = (not can_save_existing) or (not dirty)

        if (not in_draft_mode) and dirty:
            # Any uncommitted change disables downstream derived operations.
            materialize_disabled = True
            aggregate_disabled = True

        helper_children = ""
        helper_style = {
            "display": "none",
            "border": "1px solid #dbeafe",
            "borderRadius": "4px",
            "backgroundColor": "#f8fbff",
        }

        if in_draft_mode:
            # Draft guidance sequence
            if not has_name:
                next_step = "Enter a series name"
            elif not has_stack:
                next_step = "Select stack_type"
            elif not has_files:
                next_step = "Add a source file"
            elif not has_mapping:
                # Guide user from loading mapping to saving mapping, one green at a time.
                if mapping_table_data:
                    next_step = "Save Mapping"
                else:
                    next_step = "Show Mapping"
            elif not can_save_draft:
                next_step = "Complete worksheet header/data rows"
            else:
                next_step = "Save"

            missing = []
            if not has_name:
                missing.append("name")
            if not has_stack:
                missing.append("stack_type")
            if not has_files:
                missing.append("file")
            if not has_mapping:
                missing.append("saved mapping")
            if has_files and not headers_ok:
                missing.append("worksheet rows")
            missing_txt = ", ".join(missing) if missing else "none"
            helper_children = f"Draft mode | Next step: {next_step} | Missing: {missing_txt}"
            helper_style["display"] = "block"

            btn_new_color = gray
            btn_save_color = green if can_save_draft else gray
            btn_add_color = green if has_name and has_stack and not has_files else blue
            btn_show_map_color = green if (has_files and not has_mapping and not mapping_table_data) else blue
            btn_save_map_color = green if (has_files and not has_mapping and bool(mapping_table_data)) else blue
            btn_materialize_color = gray
            btn_aggregate_color = gray
            if not has_stack:
                stack_style.update({"backgroundColor": "#ecfdf3", "border": "1px solid #86efac"})
        else:
            # Saved-series guidance sequence (no persistent helper text)
            btn_new_color = blue
            if selected_series and dirty and can_save_existing:
                btn_save_color = green
                btn_materialize_color = gray
                btn_aggregate_color = gray
            elif selected_series and not has_silver and can_materialize:
                btn_materialize_color = green
                btn_new_color = blue
            elif selected_series and agg_count < 2:
                btn_aggregate_color = green
                btn_new_color = blue
            else:
                btn_new_color = green

            # Save is still available for edits on saved series, but gated by completeness.
            if btn_save_color != green:
                btn_save_color = blue if (can_save_existing and dirty) else gray
            btn_show_map_color = blue
            btn_save_map_color = blue

        return (
            series_disabled,
            delete_disabled,
            materialize_disabled,
            aggregate_disabled,
            delagg_disabled,
            del_file_disabled,
            del_map_disabled,
            btn_new_color,
            btn_add_color,
            btn_show_map_color,
            btn_save_map_color,
            btn_save_color,
            save_disabled,
            btn_materialize_color,
            btn_aggregate_color,
            btn_del_file_color,
            btn_del_agg_color,
            btn_del_map_color,
            btn_detect_color,
            stack_style,
            helper_children,
            helper_style,
        )

    @app.callback(
        Output("sm-status-alert", "duration"),
        [
            Input("sm-status-alert", "color"),
            Input("sm-status-alert", "is_open"),
        ],
        prevent_initial_call=False,
    )
    def set_status_alert_duration(color, is_open):
        if not is_open:
            return 6000
        if color in {"danger", "warning"}:
            return None
        return 6000

    @app.callback(
        [
            Output("sm-modal-unsaved-draft", "is_open"),
            Output("sm-series-dropdown", "value", allow_duplicate=True),
            Output("sm-store-pending-series", "data"),
            Output("sm-store-last-series", "data"),
            Output("sm-store-draft-series", "data", allow_duplicate=True),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("sm-store-cleanup-refresh", "data", allow_duplicate=True),
        ],
        [
            Input("sm-series-dropdown", "value"),
            Input("sm-draft-discard-continue", "n_clicks"),
            Input("sm-draft-discard-cancel", "n_clicks"),
        ],
        [
            State("sm-store-draft-series", "data"),
            State("sm-store-pending-series", "data"),
            State("sm-store-last-series", "data"),
            State("sm-store-cleanup-refresh", "data"),
            State("sm-field-name", "value"),
            State("sm-stack-type", "value"),
            State("sm-field-mapping", "value"),
            State("sm-opt-time-offset", "value"),
        ],
        prevent_initial_call=True,
    )
    def guard_unsaved_draft_series_switch(series_value, n_continue, n_cancel,
                                          draft_series_name, pending_series,
                                          last_series, cleanup_tick,
                                          name_val, stack_type_val, mapping_val, offset_val):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger == "sm-series-dropdown":
            # If the current draft name already exists on disk, Save has completed
            # and any immediate dropdown churn is post-save UI synchronization.
            # Normalize state silently instead of opening discard modal.
            if draft_series_name and (draft_series_name in data_manager.series_defs):
                normalized_value = draft_series_name
                set_value = no_update if series_value == normalized_value else normalized_value
                return (False, set_value, None, normalized_value, None,
                        no_update, no_update, no_update, no_update)

            # Programmatic transition right after Save: value is set to the
            # current draft name while draft-store clearing may still be in-flight.
            # Do not treat this as a user-initiated switch/discard case.
            if draft_series_name and series_value == draft_series_name:
                return (False, no_update, None, series_value, None,
                        no_update, no_update, no_update, no_update)

            if draft_series_name and series_value != last_series:
                # Revert immediate selection; require explicit confirmation first.
                return (True, last_series, series_value, last_series,
                        draft_series_name, no_update, no_update, no_update,
                        no_update)
            # Also check for unsaved changes in a saved series
            if series_value != last_series and last_series and not draft_series_name:
                try:
                    disk_defs = data_manager._load_series_defs()
                    # If last selected series was deleted/replaced, do not block switch.
                    if last_series not in disk_defs:
                        return (False, no_update, None, series_value, draft_series_name,
                                no_update, no_update, no_update, no_update)
                    disk_def = disk_defs.get(last_series, {})
                    disk_name = str(disk_def.get("name", ""))
                    disk_stack = str(disk_def.get("stack_type", "") or "")
                    disk_mapping = str(disk_def.get("mapping", "") or "")
                    disk_offset = str(disk_def.get("options", {}).get("time_offset [h]", "") or "")
                    form_changed = (
                        str(name_val or "") != disk_name
                        or str(stack_type_val or "") != disk_stack
                        or str(mapping_val or "") != disk_mapping
                        or str(offset_val or "") != disk_offset
                    )
                    if form_changed:
                        return (True, last_series, series_value, last_series,
                                None, no_update, no_update, no_update, no_update)
                except Exception:
                    pass
            return (False, no_update, None, series_value, draft_series_name,
                    no_update, no_update, no_update, no_update)

        if trigger == "sm-draft-discard-cancel":
            return (False, last_series, None, last_series, draft_series_name,
                    no_update, no_update, no_update, no_update)

        if trigger == "sm-draft-discard-continue":
            if pending_series is None:
                return (False, no_update, None, last_series, draft_series_name,
                        no_update, no_update, no_update, no_update)
            msg = no_update
            color = no_update
            opened = no_update
            if draft_series_name:
                discard_result = data_manager.discard_draft_series(draft_series_name)
                deleted = len(discard_result.get("deleted_files", []))
                kept = len(discard_result.get("kept_shared_files", []))
                errs = len(discard_result.get("errors", []))
                msg = (
                    f"Draft '{draft_series_name}' discarded. "
                    f"Deleted {deleted} file(s), kept {kept} shared file(s)."
                )
                color = "warning" if errs else "info"
                if errs:
                    msg += f" {errs} cleanup error(s) occurred."
                opened = True
            return (False, pending_series, None, pending_series, None,
                    msg, color, opened, (cleanup_tick or 0) + 1)

        raise PreventUpdate

    # ------------------------------------------------------------------ #
    # 1. CASCADE: series â†’ form fields + file dropdown + agg display
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-field-name", "value"),
            Output("sm-stack-type", "value"),
            Output("sm-field-mapping", "value"),
            Output("sm-opt-time-offset", "value"),
            Output("sm-file-dropdown", "options"),
            Output("sm-file-dropdown", "value"),
            Output("sm-agg-display", "children"),
            Output("sm-tag-summary", "children"),
            Output("sm-store-draft-series", "data", allow_duplicate=True),
            Output("sm-store-mapping-detach-tick", "data", allow_duplicate=True),
        ],
        Input("sm-series-dropdown", "value"),
        prevent_initial_call="initial_duplicate",
    )
    def on_series_change(series_name):
        if not series_name:
            return "", None, "", "", [], None, "(none)", "(no tags)", None, 0
        sdef = data_manager.series_defs.get(series_name, {})
        name_val = str(sdef.get("name", ""))
        stack_val = sdef.get("stack_type") or None
        mapping_val = str(sdef.get("mapping", ""))
        opts = sdef.get("options", {})
        offset_val = str(opts.get("time_offset [h]", ""))

        file_opts = _file_options(data_manager, series_name)
        file_val = file_opts[0]["value"] if file_opts else None

        agg_disp = _agg_display(data_manager, series_name)

        # Tag summary
        if tag_manager is not None:
            scfg = tag_manager.get_series_config(series_name)
            defs = tag_manager.get_tag_definitions()
            tag_names = [d["label"] for d in defs if str(d["id"]) in scfg]
            tag_summary = (", ".join(tag_names)
                           if tag_names
                           else "(no tags defined for this series)")
        else:
            tag_summary = "(tag manager not available)"

        return (name_val, stack_val, mapping_val, offset_val,
            file_opts, file_val, agg_disp, tag_summary, None, 0)

    # ------------------------------------------------------------------ #
    # 2. CASCADE: file â†’ worksheets
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-ws-dropdown", "options"),
            Output("sm-ws-dropdown", "value"),
        ],
        [Input("sm-file-dropdown", "value")],
        [
            State("sm-series-dropdown", "value"),
            State("sm-store-draft-series", "data"),
        ],
        prevent_initial_call=True,
    )
    def on_file_change(file_idx, series_name, draft_series_name):
        target_series = draft_series_name or series_name
        if target_series is None or file_idx is None:
            return [], None
        ws_opts = _ws_options(data_manager, target_series, file_idx)
        ws_val = ws_opts[0]["value"] if ws_opts else None
        return ws_opts, ws_val

    # ------------------------------------------------------------------ #
    # 3. CASCADE: worksheet â†’ header / first-data row
    #    If the rows are not yet defined, auto-detect them.
    #    On detection failure, open the manual-selection modal.
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-header-row", "value"),
            Output("sm-first-data-row", "value"),
            Output("sm-modal-detect", "is_open", allow_duplicate=True),
            Output("sm-detect-preview", "data", allow_duplicate=True),
            Output("sm-detect-preview", "columns", allow_duplicate=True),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
        ],
        [Input("sm-ws-dropdown", "value")],
        [
            State("sm-series-dropdown", "value"),
            State("sm-file-dropdown", "value"),
            State("sm-store-draft-series", "data"),
        ],
        prevent_initial_call=True,
    )
    def on_ws_change(ws_idx, series_name, file_idx, draft_series_name):
        target_series = draft_series_name or series_name
        _no_extra = (False, no_update, no_update, no_update, no_update, no_update)
        if target_series is None or file_idx is None or ws_idx is None:
            return ("", "") + _no_extra
        h, d = _header_vals(data_manager, target_series, file_idx, ws_idx)
        if h and d:
            # Rows already defined â€“ just populate the fields
            return (h, d) + _no_extra

        # Rows not yet defined â€“ attempt auto-detection
        sdef = data_manager.series_defs.get(target_series, {})
        files = sdef.get("files", [])
        if file_idx < 0 or file_idx >= len(files):
            return ("", "") + _no_extra
        file_entry = files[file_idx]
        file_path = file_entry.get("path", "")
        wss = file_entry.get("worksheets", [])
        if ws_idx < 0 or ws_idx >= len(wss):
            return ("", "") + _no_extra
        ws_name = wss[ws_idx].get("name")
        project_root = data_manager._get_project_root()
        # Normalize backslashes from Windows-generated paths in series.json
        file_path = file_path.replace('\\', '/')
        abs_path = file_path if os.path.isabs(file_path) else os.path.normpath(os.path.join(project_root, file_path))
        if not os.path.exists(abs_path):
            return ("" , "", False, no_update, no_update,
                    f"File not found: {file_path}", "warning", True)
        try:
            header_row, first_data_row, preview_df = detect_header_and_data_row(
                abs_path, worksheet=ws_name)
        except Exception as e:
            return ("", "", False, no_update, no_update,
                    f"Detection error: {e}", "danger", True)

        if header_row is not None and first_data_row is not None:
            # Detection succeeded â€“ persist and populate
            _update_ws_rows(data_manager, target_series, file_idx, ws_idx,
                            header_row, first_data_row)
            return (str(header_row), str(first_data_row), False,
                    no_update, no_update,
                    f"Auto-detected: header={header_row}, first data={first_data_row}",
                    "success", True)
        elif preview_df is not None:
            # Detection failed â€“ open manual selection modal with preview
            preview = preview_df.iloc[:10, :5].fillna("").astype(str)
            preview.insert(0, "Row#", range(len(preview)))
            cols = [{"name": c, "id": c} for c in preview.columns]
            data = preview.to_dict("records")
            return ("", "", True, data, cols, no_update, no_update, no_update)
        else:
            return ("", "", False, no_update, no_update,
                    "Auto-detection failed and no preview available.",
                    "danger", True)

    # ------------------------------------------------------------------ #
    # 4. SAVE series
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-series-dropdown", "options", allow_duplicate=True),
            Output("sm-series-dropdown", "value", allow_duplicate=True),
            Output("sm-store-last-series", "data", allow_duplicate=True),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("store-series-refresh", "data", allow_duplicate=True),
            Output("sm-store-draft-series", "data", allow_duplicate=True),
            Output("sm-store-cleanup-refresh", "data", allow_duplicate=True),
            Output("sm-store-mapping-detach-tick", "data", allow_duplicate=True),
        ],
        Input("sm-btn-save", "n_clicks"),
        [
            State("sm-series-dropdown", "value"),
            State("sm-store-draft-series", "data"),
            State("sm-field-name", "value"),
            State("sm-stack-type", "value"),
            State("sm-opt-time-offset", "value"),
            State("sm-header-row", "value"),
            State("sm-first-data-row", "value"),
            State("sm-file-dropdown", "value"),
            State("sm-ws-dropdown", "value"),
            State("store-series-refresh", "data"),
            State("sm-store-cleanup-refresh", "data"),
        ],
        prevent_initial_call=True,
    )
    def on_save(n, series_name, draft_series_name,
                name_val, stack_type, offset,
                header_row, first_data_row, file_idx, ws_idx,
                refresh_tick, cleanup_tick):
        target_series = draft_series_name or series_name
        if not target_series:
            raise PreventUpdate

        if draft_series_name and draft_series_name not in data_manager.series_defs:
            created = data_manager.create_series(draft_series_name)
            if not created:
                opts = _series_options(data_manager)
                return (opts, no_update,
                        no_update,
                        f"Failed to create draft '{draft_series_name}' (already exists).",
                    "danger", True, no_update, draft_series_name, no_update, no_update)

        # Update header/data row in the live series_defs before save
        sdef = data_manager.series_defs.get(target_series, {})
        files = sdef.get("files", [])
        if (file_idx is not None and ws_idx is not None
                and 0 <= file_idx < len(files)):
            wss = files[file_idx].get("worksheets", [])
            if 0 <= ws_idx < len(wss):
                try:
                    wss[ws_idx]["header_row"] = int(header_row)
                except (TypeError, ValueError):
                    pass
                try:
                    wss[ws_idx]["first_data_row"] = int(first_data_row)
                except (TypeError, ValueError):
                    pass

        # â”€â”€ Mandatory field validation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        errors = []
        if not (name_val or "").strip():
            errors.append("â€¢ name is required")
        if not (stack_type or "").strip():
            errors.append("â€¢ stack_type is required")
        # New drafts must be fully defined before first commit; existing series
        # can be edited/saved incrementally and validated later for materialize.
        if draft_series_name:
            mapping_path = sdef.get("mapping", "")
            if not (mapping_path or "").strip():
                errors.append("â€¢ mapping file is required (use Save Mapping after defining the column mapping)")
            if not files:
                errors.append("â€¢ at least one bronze file must be added")
            else:
                for fi, fentry in enumerate(files):
                    wss = fentry.get("worksheets", [])
                    if not wss:
                        errors.append(f"â€¢ file {fi + 1} has no worksheets configured")
                    for wi, ws in enumerate(wss):
                        if ws.get("header_row") is None:
                            errors.append(
                                f"â€¢ file {fi + 1} worksheet '{ws.get('name', wi + 1)}': "
                                "header_row is missing")
                        if ws.get("first_data_row") is None:
                            errors.append(
                                f"â€¢ file {fi + 1} worksheet '{ws.get('name', wi + 1)}': "
                                "first_data_row is missing")
        if errors:
            msg = "Cannot save â€” fix the following:\n" + "\n".join(errors)
            return (no_update, no_update, no_update, msg, "danger", True,
                    no_update, draft_series_name, no_update, no_update)
        # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

        fields = {"name": name_val or "", "stack_type": stack_type or ""}
        options = {"time_offset [h]": offset or ""}
        data_manager.save_series(target_series, fields=fields,
                                 options=options, files=files)

        opts = _series_options(data_manager)
        return (opts, target_series, target_series,
                f"Series '{target_series}' saved.", "success", True,
            (refresh_tick or 0) + 1, None, (cleanup_tick or 0) + 1, 0)

    # ------------------------------------------------------------------ #
    # 5. NEW series â€“ open modal
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("sm-modal-new", "is_open"),
        [
            Input("sm-btn-new", "n_clicks"),
            Input("sm-new-confirm", "n_clicks"),
            Input("sm-new-cancel", "n_clicks"),
        ],
        State("sm-modal-new", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_new_modal(n_open, n_confirm, n_cancel, is_open):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger == "sm-btn-new":
            return True
        return False

    @app.callback(
        [
            Output("sm-field-name", "value", allow_duplicate=True),
            Output("sm-stack-type", "value", allow_duplicate=True),
            Output("sm-field-mapping", "value", allow_duplicate=True),
            Output("sm-opt-time-offset", "value", allow_duplicate=True),
            Output("sm-file-dropdown", "options", allow_duplicate=True),
            Output("sm-file-dropdown", "value", allow_duplicate=True),
            Output("sm-ws-dropdown", "options", allow_duplicate=True),
            Output("sm-ws-dropdown", "value", allow_duplicate=True),
            Output("sm-header-row", "value", allow_duplicate=True),
            Output("sm-first-data-row", "value", allow_duplicate=True),
            Output("sm-agg-display", "children", allow_duplicate=True),
            Output("sm-tag-summary", "children", allow_duplicate=True),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("sm-store-draft-series", "data", allow_duplicate=True),
        ],
        Input("sm-new-confirm", "n_clicks"),
        State("sm-new-name-input", "value"),
        State("sm-store-draft-series", "data"),
        prevent_initial_call=True,
    )
    def on_new_series(n, new_name, current_draft):
        if not new_name or not new_name.strip():
            raise PreventUpdate
        new_name = new_name.strip()
        if new_name in data_manager.series_defs:
            return (
                no_update, no_update, no_update, no_update,
                no_update, no_update, no_update, no_update,
                no_update, no_update, no_update, no_update,
                f"Series '{new_name}' already exists.", "warning", True,
                current_draft,
            )

        # Draft mode: do not persist yet; Save will commit to series.json.
        return (
            new_name,
            None,
            "",
            "",
            [],
            None,
            [],
            None,
            "",
            "",
            "(none)",
            "(draft series - no tags yet)",
            f"Draft '{new_name}' initialized. Click Save to commit.",
            "info",
            True,
            new_name,
        )

    @app.callback(
        [
            Output("sm-mapping-table", "data", allow_duplicate=True),
            Output("sm-mapping-table", "dropdown", allow_duplicate=True),
            Output("sm-mapping-table", "style_data_conditional", allow_duplicate=True),
            Output("sm-store-mapping-schema-names", "data", allow_duplicate=True),
            Output("sm-store-mapping-file-cols", "data", allow_duplicate=True),
            Output("sm-unmapped-badge", "children", allow_duplicate=True),
            Output("sm-unmapped-badge", "className", allow_duplicate=True),
        ],
        Input("sm-new-confirm", "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_mapping_on_new_series(n):
        if not n:
            raise PreventUpdate
        return [], {}, [], [], [], "0", "badge bg-secondary"

    # ------------------------------------------------------------------ #
    # 6. DELETE series â€“ open modal, execute
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-modal-delete", "is_open"),
            Output("sm-delete-body", "children"),
        ],
        [
            Input("sm-btn-delete", "n_clicks"),
            Input("sm-del-keep", "n_clicks"),
            Input("sm-del-files", "n_clicks"),
            Input("sm-del-cancel", "n_clicks"),
        ],
        [
            State("sm-modal-delete", "is_open"),
            State("sm-series-dropdown", "value"),
        ],
        prevent_initial_call=True,
    )
    def toggle_delete_modal(n_open, n_keep, n_files, n_cancel,
                            is_open, series_name):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger == "sm-btn-delete" and series_name:
            assoc = data_manager.get_associated_files(series_name)
            if assoc:
                body = html.Div([
                    html.P(f"Delete series '{series_name}'?"),
                    html.P("The following associated files were found:"),
                    html.Ul([html.Li(f) for f in assoc]),
                    html.P("Source files in bronze are not deleted here; they are only detached from this series."),
                    html.P("Select Next to continue to final confirmation."),
                ])
            else:
                body = html.Div([
                    html.P(f"Delete series '{series_name}'? No associated files found."),
                    html.P("Select Next to continue to final confirmation."),
                ])
            return True, body
        return False, ""

    @app.callback(
        [
            Output("sm-modal-delete-confirm", "is_open"),
            Output("sm-delete-confirm-body", "children"),
            Output("sm-store-delete-mode", "data"),
        ],
        [
            Input("sm-del-keep", "n_clicks"),
            Input("sm-del-files", "n_clicks"),
            Input("sm-del-final-cancel", "n_clicks"),
        ],
        State("sm-series-dropdown", "value"),
        prevent_initial_call=True,
    )
    def open_delete_confirm_modal(n_keep, n_files, n_cancel, series_name):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger == "sm-del-final-cancel":
            return False, "", None

        if not series_name:
            raise PreventUpdate

        assoc = data_manager.get_associated_files(series_name)
        if trigger == "sm-del-files":
            body = html.Div([
                html.P(f"Final confirmation: delete series '{series_name}', detach source files, and delete non-source artifacts now."),
                html.P("This action cannot be undone."),
                html.P("Source files in bronze are retained and can be removed later via Cleanup."),
                html.P(f"Associated entries detected: {len(assoc)}"),
            ])
            return True, body, "files"

        body = html.Div([
            html.P(f"Final confirmation: delete series '{series_name}' and detach source files only."),
            html.P("Series metadata will be removed; source files remain in bronze."),
            html.P("Derived artifacts are kept until Cleanup is run."),
            html.P(f"Associated entries detected: {len(assoc)}"),
        ])
        return True, body, "keep"

    @app.callback(
        [
            Output("sm-modal-delete-confirm", "is_open", allow_duplicate=True),
            Output("sm-series-dropdown", "options", allow_duplicate=True),
            Output("sm-series-dropdown", "value", allow_duplicate=True),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("store-series-refresh", "data", allow_duplicate=True),
            Output("sm-store-cleanup-refresh", "data", allow_duplicate=True),
        ],
        Input("sm-del-final-confirm", "n_clicks"),
        [
            State("sm-series-dropdown", "value"),
            State("sm-store-delete-mode", "data"),
            State("store-series-refresh", "data"),
            State("sm-store-cleanup-refresh", "data"),
        ],
        prevent_initial_call=True,
    )
    def on_delete_series(n_confirm, series_name, delete_mode, refresh_tick,
                         cleanup_tick):
        if not series_name:
            raise PreventUpdate
        delete_files = delete_mode == "files"
        if delete_mode not in {"keep", "files"}:
            return (False, no_update, no_update,
                    "Delete mode not selected. Re-open delete dialog.",
                    "warning", True, no_update, no_update)
        result = data_manager.delete_series(series_name,
                                            delete_associated_files=delete_files)
        if not result["deleted"]:
            return (False, no_update, no_update,
                    f"Failed to delete '{series_name}'.", "danger", True,
                    no_update, no_update)
        errs = result.get("errors", [])
        err_msg = "; ".join(f"{p}: {e}" for p, e in errs) if errs else ""
        opts = _series_options(data_manager)
        new_val = opts[0]["value"] if opts else None
        msg = f"Deleted '{series_name}'."
        if err_msg:
            msg += f" Errors: {err_msg}"
        return (False, opts, new_val, msg, "success", True,
            (refresh_tick or 0) + 1, (cleanup_tick or 0) + 1)

    @app.callback(
        [
            Output("sm-btn-cleanup", "color"),
            Output("sm-btn-cleanup", "children"),
        ],
        Input("sm-store-cleanup-refresh", "data"),
        prevent_initial_call=False,
    )
    def update_cleanup_button_state(_cleanup_tick):
        orphan_count = len(data_manager.find_orphaned_files())
        if orphan_count > 0:
            return "danger", f"Cleanup ({orphan_count})"
        return "dark", "Cleanup"

    # ------------------------------------------------------------------ #
    # 6b. CLEANUP orphaned files â€“ open modal, execute
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-modal-cleanup", "is_open"),
            Output("sm-cleanup-table", "data"),
        ],
        [
            Input("sm-btn-cleanup", "n_clicks"),
            Input("sm-cleanup-cancel", "n_clicks"),
        ],
        [State("sm-modal-cleanup", "is_open")],
        prevent_initial_call=True,
    )
    def toggle_cleanup_modal(n_cleanup, n_cancel, is_open):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]
        
        if trigger == "sm-btn-cleanup":
            # Find orphaned files
            orphaned = data_manager.find_orphaned_files()
            table_data = []
            for f in orphaned:
                size_kb = f.get("size", 0) / 1024 if f.get("size") else 0
                table_data.append({
                    "rel_path": f.get("rel_path", ""),
                    "size_kb": f"{size_kb:.1f}",
                    "created_dt": f.get("created_dt", f.get("created", "N/A")),
                })
            return True, table_data
        
        # Cancel button
        return False, []

    @app.callback(
        [
            Output("sm-modal-cleanup", "is_open", allow_duplicate=True),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("sm-store-cleanup-refresh", "data", allow_duplicate=True),
        ],
        Input("sm-cleanup-confirm", "n_clicks"),
        State("sm-store-cleanup-refresh", "data"),
        prevent_initial_call=True,
    )
    def on_cleanup_confirm(n_clicks, cleanup_tick):
        if not n_clicks:
            raise PreventUpdate
        
        orphaned = data_manager.find_orphaned_files()
        deleted_count = 0
        failed_count = 0
        
        for f in orphaned:
            file_path = f.get("path", "")
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete {file_path}: {e}")
                failed_count += 1
        
        msg = f"Cleanup complete: {deleted_count} file(s) deleted."
        if failed_count > 0:
            msg += f" {failed_count} file(s) failed."
            color = "warning"
        else:
            color = "success"
        
        return False, msg, color, True, (cleanup_tick or 0) + 1

    # ------------------------------------------------------------------ #
    # 7. ADD FILE via dcc.Upload
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-file-dropdown", "options", allow_duplicate=True),
            Output("sm-file-dropdown", "value", allow_duplicate=True),
            Output("sm-modal-overwrite", "is_open", allow_duplicate=True),
            Output("sm-store-upload-temp", "data"),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("sm-store-cleanup-refresh", "data", allow_duplicate=True),
        ],
        Input("sm-file-upload", "contents"),
        [
            State("sm-file-upload", "filename"),
            State("sm-series-dropdown", "value"),
            State("sm-store-draft-series", "data"),
            State("sm-store-cleanup-refresh", "data"),
        ],
        prevent_initial_call=True,
    )
    def on_file_upload(contents, filename, series_name, draft_series_name,
                       cleanup_tick):
        target_series = draft_series_name or series_name
        if not contents or not target_series:
            raise PreventUpdate
        # Decode the uploaded file content and write to a temp file
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
        tmp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, filename)
        with open(tmp_path, "wb") as f:
            f.write(decoded)

        bronze_path, status = data_manager.import_file_to_bronze(tmp_path)

        if status == "exists":
            linked_series = []
            for sname, sdef in data_manager.series_defs.items():
                if sname == target_series:
                    continue
                for fe in sdef.get("files", []):
                    if fe.get("path") == bronze_path:
                        linked_series.append(sname)
                        break
            body = (
                f"A file with this name already exists in bronze: {os.path.basename(bronze_path)}."
            )
            if linked_series:
                body += " Linked to series: " + ", ".join(sorted(linked_series)) + "."
            # Ask whether to overwrite â€“ store temp path for later
            return (no_update, no_update, True,
                    {"tmp_path": tmp_path, "filename": filename, "bronze_path": bronze_path},
                    body, "warning", True, no_update)

        # File was copied (or already in bronze)
        out = _finalise_file_add(data_manager, target_series,
                                 bronze_path, tmp_path)
        return out + ((cleanup_tick or 0) + 1,)

    @app.callback(
        [
            Output("sm-file-dropdown", "options", allow_duplicate=True),
            Output("sm-file-dropdown", "value", allow_duplicate=True),
            Output("sm-modal-overwrite", "is_open", allow_duplicate=True),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("sm-store-cleanup-refresh", "data", allow_duplicate=True),
        ],
        [
            Input("sm-overwrite-attach", "n_clicks"),
            Input("sm-overwrite-yes", "n_clicks"),
            Input("sm-overwrite-no", "n_clicks"),
        ],
        [
            State("sm-store-upload-temp", "data"),
            State("sm-series-dropdown", "value"),
            State("sm-store-draft-series", "data"),
            State("sm-store-cleanup-refresh", "data"),
        ],
        prevent_initial_call=True,
    )
    def on_overwrite_decision(n_attach, n_yes, n_no, upload_data, series_name,
                              draft_series_name, cleanup_tick):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]

        def _cleanup_tmp_file(path):
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

        if trigger == "sm-overwrite-no" or not upload_data:
            _cleanup_tmp_file(upload_data.get("tmp_path") if upload_data else None)
            return (no_update, no_update, False, no_update,
                    no_update, no_update, no_update)
        target_series = draft_series_name or series_name
        if not target_series:
            raise PreventUpdate
        tmp_path = upload_data["tmp_path"]
        if trigger == "sm-overwrite-attach":
            bronze_path = upload_data.get("bronze_path")
            if not bronze_path:
                # Fallback if older temp payload is encountered.
                bronze_path = data_manager.import_file_to_bronze(tmp_path)[0]
            opts, val, _, _, msg, color, is_open = _finalise_file_add(
                data_manager, target_series, bronze_path, tmp_path)
            return opts, val, False, msg, color, is_open, (cleanup_tick or 0) + 1

        bronze_path = data_manager.overwrite_file_in_bronze(tmp_path)
        opts, val, _, _, msg, color, is_open = _finalise_file_add(
            data_manager, target_series, bronze_path, tmp_path)
        return opts, val, False, msg, color, is_open, (cleanup_tick or 0) + 1

    # ------------------------------------------------------------------ #
    # 8. DELETE FILE
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-file-dropdown", "options", allow_duplicate=True),
            Output("sm-file-dropdown", "value", allow_duplicate=True),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("sm-store-cleanup-refresh", "data", allow_duplicate=True),
        ],
        Input("sm-btn-del-file", "n_clicks"),
        [
            State("sm-series-dropdown", "value"),
            State("sm-file-dropdown", "value"),
            State("sm-store-draft-series", "data"),
            State("sm-store-cleanup-refresh", "data"),
        ],
        prevent_initial_call=True,
    )
    def on_delete_file(n, series_name, file_idx, draft_series_name,
                       cleanup_tick):
        target_series = draft_series_name or series_name
        if target_series is None or file_idx is None:
            raise PreventUpdate
        sdef = data_manager.series_defs.get(target_series, {})
        files = sdef.get("files", [])
        if 0 <= file_idx < len(files):
            del files[file_idx]
            sdef["files"] = files
            data_manager.series_defs[target_series] = sdef
        file_opts = _file_options(data_manager, target_series)
        new_val = file_opts[0]["value"] if file_opts else None
        return (file_opts, new_val, "File removed from series.", "info", True,
            (cleanup_tick or 0) + 1)

    # ------------------------------------------------------------------ #
    # 9. DETECT ROWS
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-header-row", "value", allow_duplicate=True),
            Output("sm-first-data-row", "value", allow_duplicate=True),
            Output("sm-modal-detect", "is_open"),
            Output("sm-detect-preview", "data"),
            Output("sm-detect-preview", "columns"),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
        ],
        Input("sm-btn-detect", "n_clicks"),
        [
            State("sm-series-dropdown", "value"),
            State("sm-file-dropdown", "value"),
            State("sm-ws-dropdown", "value"),
            State("sm-store-draft-series", "data"),
        ],
        prevent_initial_call=True,
    )
    def on_detect_rows(n, series_name, file_idx, ws_idx, draft_series_name):
        target_series = draft_series_name or series_name
        if not target_series or file_idx is None or ws_idx is None:
            return (no_update, no_update, False, no_update, no_update,
                    "Select a file and worksheet first.", "warning", True)
        sdef = data_manager.series_defs.get(target_series, {})
        files = sdef.get("files", [])
        if file_idx < 0 or file_idx >= len(files):
            raise PreventUpdate
        file_entry = files[file_idx]
        file_path = file_entry.get("path", "")
        wss = file_entry.get("worksheets", [])
        if ws_idx < 0 or ws_idx >= len(wss):
            raise PreventUpdate
        ws_name = wss[ws_idx].get("name")
        project_root = data_manager._get_project_root()
        # Normalize backslashes from Windows-generated paths in series.json
        file_path = file_path.replace('\\', '/')
        abs_path = file_path if os.path.isabs(file_path) else os.path.normpath(os.path.join(project_root, file_path))
        try:
            header_row, first_data_row, preview_df = detect_header_and_data_row(
                abs_path, worksheet=ws_name)
        except Exception as e:
            return (no_update, no_update, False, no_update, no_update,
                    f"Detection error: {e}", "danger", True)

        if header_row is not None and first_data_row is not None:
            # Auto-detection succeeded â€” apply immediately
            _update_ws_rows(data_manager, target_series, file_idx, ws_idx,
                            header_row, first_data_row)
            return (str(header_row), str(first_data_row), False,
                    no_update, no_update,
                    f"Detected header={header_row}, data={first_data_row}",
                    "success", True)
        elif preview_df is not None:
            # Show manual selection modal
            preview = preview_df.iloc[:10, :5].fillna("").astype(str)
            preview.insert(0, "Row#", range(len(preview)))
            cols = [{"name": c, "id": c} for c in preview.columns]
            data = preview.to_dict("records")
            return (no_update, no_update, True, data, cols,
                    no_update, no_update, no_update)
        else:
            return (no_update, no_update, False, no_update, no_update,
                    "Auto-detection failed and no preview available.",
                    "danger", True)

    @app.callback(
        [
            Output("sm-header-row", "value", allow_duplicate=True),
            Output("sm-first-data-row", "value", allow_duplicate=True),
            Output("sm-modal-detect", "is_open", allow_duplicate=True),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
        ],
        [
            Input("sm-detect-apply", "n_clicks"),
            Input("sm-detect-cancel", "n_clicks"),
        ],
        [
            State("sm-detect-header", "value"),
            State("sm-detect-data", "value"),
            State("sm-series-dropdown", "value"),
            State("sm-file-dropdown", "value"),
            State("sm-ws-dropdown", "value"),
            State("sm-store-draft-series", "data"),
        ],
        prevent_initial_call=True,
    )
    def on_detect_manual(n_apply, n_cancel, hdr, dta, series_name, file_idx,
                         ws_idx, draft_series_name):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger == "sm-detect-cancel":
            return no_update, no_update, False, no_update, no_update, no_update
        target_series = draft_series_name or series_name
        if hdr is None or dta is None:
            return (no_update, no_update, no_update,
                    "Enter both row numbers.", "warning", True)
        try:
            hdr, dta = int(hdr), int(dta)
        except (TypeError, ValueError):
            return (no_update, no_update, no_update,
                    "Invalid row numbers.", "warning", True)
        if dta <= hdr:
            return (no_update, no_update, no_update,
                    "First data row must be > header row.", "warning", True)
        if not target_series or file_idx is None or ws_idx is None:
            return (no_update, no_update, no_update,
                "Select a file and worksheet first.", "warning", True)
        _update_ws_rows(data_manager, target_series, file_idx, ws_idx, hdr, dta)
        return (str(hdr), str(dta), False,
                f"Manual: header={hdr}, data={dta}", "success", True)

    # ------------------------------------------------------------------ #
    # 10. MATERIALIZE
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("sm-agg-display", "children", allow_duplicate=True),
        ],
        Input("sm-btn-materialize", "n_clicks"),
        State("sm-series-dropdown", "value"),
        prevent_initial_call=True,
    )
    def on_materialize(n, series_name):
        if not series_name:
            raise PreventUpdate
        issues = data_manager.validate_for_materialization(series_name)
        if issues:
            msg = "Validation failed:\n" + "\n".join(issues)
            return msg, "danger", True, no_update
        ok = data_manager.materialize_silver_layer(series_name)
        if ok:
            agg_disp = _agg_display(data_manager, series_name)
            return (f"'{series_name}': silver layer materialized.",
                    "success", True, agg_disp)
        return f"'{series_name}': materialization failed.", "danger", True, no_update

    # ------------------------------------------------------------------ #
    # 11. AGGREGATE
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("sm-agg-display", "children", allow_duplicate=True),
        ],
        Input("sm-btn-aggregate", "n_clicks"),
        [
            State("sm-series-dropdown", "value"),
            State("sm-agg-interval", "value"),
        ],
        prevent_initial_call=True,
    )
    def on_aggregate(n, series_name, interval):
        if not series_name:
            raise PreventUpdate
        try:
            iv = int(interval)
            if iv <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return ("Invalid interval â€“ enter a positive integer.",
                    "warning", True, no_update)
        try:
            ok = data_manager.aggregate_and_store_series(series_name, interval_minutes=iv)
        except Exception as e:
            return (f"Aggregation failed: {e}", "danger", True, no_update)
        if ok:
            agg_disp = _agg_display(data_manager, series_name)
            return (f"Aggregated {iv} min for '{series_name}'.",
                    "success", True, agg_disp)
        return "Aggregation failed.", "danger", True, no_update

    # ------------------------------------------------------------------ #
    # 12. DELETE AGGREGATION â€“ open modal
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-modal-delagg", "is_open"),
            Output("sm-delagg-text", "children"),
            Output("sm-delagg-radio", "options"),
            Output("sm-delagg-radio", "value"),
        ],
        [
            Input("sm-btn-del-agg", "n_clicks"),
            Input("sm-delagg-confirm", "n_clicks"),
            Input("sm-delagg-cancel", "n_clicks"),
        ],
        State("sm-series-dropdown", "value"),
        prevent_initial_call=True,
    )
    def toggle_delagg_modal(n_open, n_confirm, n_cancel, series_name):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger == "sm-btn-del-agg" and series_name:
            agg_list = data_manager.series_defs.get(series_name, {}).get("aggregations", [])
            if not agg_list:
                return False, "No aggregations.", [], None
            radio_opts = [{"label": f"{v} min", "value": str(v)} for v in agg_list]
            radio_opts.append({"label": "All", "value": "all"})
            return True, f"Select aggregation to delete for '{series_name}':", radio_opts, None
        return False, "", [], None

    @app.callback(
        [
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("sm-agg-display", "children", allow_duplicate=True),
        ],
        Input("sm-delagg-confirm", "n_clicks"),
        [
            State("sm-delagg-radio", "value"),
            State("sm-series-dropdown", "value"),
        ],
        prevent_initial_call=True,
    )
    def on_delagg_confirm(n, choice, series_name):
        if not choice or not series_name:
            raise PreventUpdate
        if choice == "all":
            removed = data_manager.delete_all_aggregations(series_name)
            msg = f"Deleted all {removed} aggregation(s)."
        else:
            iv = int(choice)
            ok = data_manager.delete_aggregation(series_name, iv)
            msg = f"Deleted {iv} min aggregation." if ok else "Deletion failed."
        agg_disp = _agg_display(data_manager, series_name)
        return msg, "success", True, agg_disp

    # ------------------------------------------------------------------ #
    # 13. SHOW MAPPING
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-mapping-table", "data"),
            Output("sm-mapping-table", "dropdown"),
            Output("sm-mapping-table", "style_data_conditional"),
            Output("sm-store-mapping-schema-names", "data"),
            Output("sm-store-mapping-file-cols", "data"),
            Output("sm-unmapped-badge", "children"),
            Output("sm-unmapped-badge", "className"),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
        ],
        [
            Input("sm-series-dropdown", "value"),
            Input("sm-store-draft-series", "data"),
            Input("sm-btn-show-map", "n_clicks"),
        ],
        prevent_initial_call='initial_duplicate',
    )
    def on_show_mapping(series_name, draft_series_name, n):
        target = draft_series_name or series_name
        if not target:
            return ([], {}, [], None, None, "0", "badge bg-secondary",
                    no_update, no_update, no_update)

        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""
        explicit_show = trigger == "sm-btn-show-map"

        # Ensure draft stub exists in memory before calling define_mapping
        if draft_series_name and draft_series_name not in data_manager.series_defs:
            data_manager.create_series(draft_series_name)

        # Keep table aligned with selected series at startup/switch without noisy warnings.
        sdef = data_manager.series_defs.get(target, {})
        if not sdef.get("files"):
            if explicit_show:
                return ([], {}, [], None, None, "0", "badge bg-secondary",
                        "Add at least one bronze file before loading the mapping.",
                        "warning", True)
            return ([], {}, [], None, None, "0", "badge bg-secondary",
                    no_update, no_update, no_update)

        # Auto-load mapping only when series points to a mapping path that exists.
        # This keeps detached mappings visually empty after Save.
        mapping_rel = str(sdef.get("mapping", "") or "").strip()
        mapping_abs = data_manager._get_mapping_file_for_series(target) if mapping_rel else None
        has_valid_saved_mapping = bool(mapping_rel and mapping_abs and os.path.exists(mapping_abs))
        if (not has_valid_saved_mapping) and (not explicit_show):
            return ([], {}, [], None, None, "0", "badge bg-secondary",
                    no_update, no_update, no_update)

        try:
            mapping, schema_names, file_columns = data_manager.define_mapping(target)
        except Exception as e:
            return ([], {}, [], None, None, "0", "badge bg-secondary",
                    f"Mapping error: {e}", "danger", True)

        # Build dropdown options for the DataTable columns
        if schema_names:
            schema_dd = [{"label": s, "value": s} for s in schema_names]
        else:
            # Loaded from saved file â€“ extract from the mapping itself
            schema_dd = [{"label": m["schema_column"], "value": m["schema_column"]}
                         for m in mapping if m.get("schema_column")]
            schema_names = [m["schema_column"] for m in mapping if m.get("schema_column")]

        if file_columns:
            file_dd = [{"label": c, "value": c} for c in file_columns]
        else:
            # Extract from mapping
            file_cols_set = sorted({m["file_column"] for m in mapping
                                    if m.get("file_column")})
            file_dd = [{"label": c, "value": c} for c in file_cols_set]
            file_columns = file_cols_set

        dropdown = {
            "schema_column": {"options": schema_dd},
            "file_column": {"options": file_dd},
        }

        # Build conditional styles
        style_cond = _build_style_conditions(mapping)

        # Unmapped badge
        mapped_set = {m["file_column"] for m in mapping if m.get("file_column")}
        unmapped = [c for c in (file_columns or []) if c not in mapped_set]
        badge_text = str(len(unmapped)) if unmapped else "0"
        badge_class = "badge bg-danger" if unmapped else "badge bg-success"

        return (mapping, dropdown, style_cond,
                schema_names if isinstance(schema_names, list) else list(schema_names),
                list(file_columns) if file_columns else [],
                badge_text, badge_class,
                no_update, no_update, no_update)

    # ------------------------------------------------------------------ #
    # 14. MAPPING TABLE EDIT â†’ update styles + unmapped badge
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-mapping-table", "style_data_conditional", allow_duplicate=True),
            Output("sm-unmapped-badge", "children", allow_duplicate=True),
            Output("sm-unmapped-badge", "className", allow_duplicate=True),
        ],
        Input("sm-mapping-table", "data"),
        State("sm-store-mapping-file-cols", "data"),
        prevent_initial_call=True,
    )
    def on_mapping_edit(table_data, file_columns):
        if not table_data:
            raise PreventUpdate
        style_cond = _build_style_conditions(table_data)
        mapped_set = {r["file_column"] for r in table_data if r.get("file_column")}
        unmapped = [c for c in (file_columns or []) if c not in mapped_set]
        badge_text = str(len(unmapped)) if unmapped else "0"
        badge_class = "badge bg-danger" if unmapped else "badge bg-success"
        return style_cond, badge_text, badge_class

    # ------------------------------------------------------------------ #
    # 15. SAVE MAPPING
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-field-mapping", "value", allow_duplicate=True),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("sm-store-cleanup-refresh", "data", allow_duplicate=True),
        ],
        Input("sm-btn-save-map", "n_clicks"),
        [
            State("sm-series-dropdown", "value"),
            State("sm-store-draft-series", "data"),
            State("sm-mapping-table", "data"),
            State("sm-store-cleanup-refresh", "data"),
        ],
        prevent_initial_call=True,
    )
    def on_save_mapping(n, series_name, draft_series_name, table_data,
                        cleanup_tick):
        target = draft_series_name or series_name
        if not target or not table_data:
            raise PreventUpdate
        if draft_series_name and draft_series_name not in data_manager.series_defs:
            # Draft not yet created â€” create the stub so the mapping can be saved
            data_manager.create_series(draft_series_name)
        out_path = data_manager.save_mapping(target, table_data)
        # Show relative path in the field (matches series.json exactly);
        # keep the absolute path only in the status banner for full context.
        rel_path = data_manager.series_defs.get(target, {}).get("mapping", out_path)
        return (rel_path, f"Mapping saved to {out_path}", "success", True,
            (cleanup_tick or 0) + 1)

    # ------------------------------------------------------------------ #
    # 16. DELETE MAPPING
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("sm-modal-del-map", "is_open"),
            Output("sm-del-map-body", "children"),
        ],
        [
            Input("sm-btn-del-map", "n_clicks"),
            Input("sm-del-map-cancel", "n_clicks"),
            Input("sm-del-map-confirm", "n_clicks"),
        ],
        [
            State("sm-series-dropdown", "value"),
            State("sm-store-draft-series", "data"),
        ],
        prevent_initial_call=True,
    )
    def toggle_delete_mapping_modal(n_open, n_cancel, n_confirm, series_name,
                                    draft_series_name):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger == "sm-btn-del-map":
            target_series = draft_series_name or series_name
            if not target_series:
                raise PreventUpdate
            body = html.Div([
                html.P(f"Detach mapping from series '{target_series}'?"),
                html.P("This only stages the change in memory."),
                html.P("Click Save to commit it to series.json."),
                html.P("The mapping file is not deleted here; Cleanup handles orphaned files."),
            ])
            return True, body

        return False, ""

    @app.callback(
        [
            Output("sm-mapping-table", "data", allow_duplicate=True),
            Output("sm-unmapped-badge", "children", allow_duplicate=True),
            Output("sm-unmapped-badge", "className", allow_duplicate=True),
            Output("sm-field-mapping", "value", allow_duplicate=True),
            Output("sm-status-alert", "children", allow_duplicate=True),
            Output("sm-status-alert", "color", allow_duplicate=True),
            Output("sm-status-alert", "is_open", allow_duplicate=True),
            Output("sm-modal-del-map", "is_open", allow_duplicate=True),
            Output("sm-store-cleanup-refresh", "data", allow_duplicate=True),
            Output("sm-store-mapping-detach-tick", "data", allow_duplicate=True),
        ],
        Input("sm-del-map-confirm", "n_clicks"),
        [
            State("sm-series-dropdown", "value"),
            State("sm-store-draft-series", "data"),
            State("sm-store-cleanup-refresh", "data"),
            State("sm-store-mapping-detach-tick", "data"),
        ],
        prevent_initial_call=True,
    )
    def on_delete_mapping(n, series_name, draft_series_name, cleanup_tick, detach_tick):
        target_series = draft_series_name or series_name
        if not target_series:
            raise PreventUpdate

        sdef = data_manager.series_defs.get(target_series, {})
        had_mapping = bool((sdef.get("mapping", "") or "").strip())
        sdef["mapping"] = ""
        data_manager.series_defs[target_series] = sdef

        msg = "Mapping detached in memory. Click Save to persist."
        if not had_mapping:
            msg = "No persisted mapping was set. Cleared mapping state in memory. Click Save to persist."

        return (
            [],
            "0",
            "badge bg-secondary",
            "",
            msg,
            "info",
            True,
            False,  # Close modal
            cleanup_tick,
            (detach_tick or 0) + 1,  # Increment to trigger dirty state
        )

    # ------------------------------------------------------------------ #
    # 17. TAG MANAGER: Populate range table when series / tag changes
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("tm-range-table", "data"),
            Output("tm-series-label", "children"),
            Output("tm-store-ranges-dirty", "data", allow_duplicate=True),
        ],
        [
            Input("sm-series-dropdown", "value"),
            Input("tm-tag-dropdown", "value"),
        ],
        prevent_initial_call="initial_duplicate",
    )
    def on_tag_range_update(series_name, tag_id):
        if not series_name or tag_id is None or tag_manager is None:
            return [], "", False
        defn = tag_manager.get_tag_definition(tag_id)
        if defn is None:
            return [], series_name, False
        categories = defn.get("categories", [])
        scfg = tag_manager.get_series_config(series_name)
        tag_ranges = scfg.get(str(tag_id), {})
        rows = []
        for cat in categories:
            raw = tag_ranges.get(cat, [])
            formatted = ", ".join(
                f"{lo}\u2013{hi}" for lo, hi in raw
            ) if raw else ""
            rows.append({"category": cat, "ranges": formatted})
        return rows, series_name, False

    # ------------------------------------------------------------------ #
    # 18. TAG MANAGER: Add Tag definition
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("tm-def-table", "data", allow_duplicate=True),
            Output("tm-def-status", "children", allow_duplicate=True),
            Output("tm-store-def-dirty", "data", allow_duplicate=True),
        ],
        Input("tm-btn-add-def", "n_clicks"),
        State("tm-def-table", "data"),
        prevent_initial_call=True,
    )
    def on_add_tag_def(n, rows):
        if not n:
            raise PreventUpdate
        next_id = max((r["id"] for r in rows), default=0) + 1
        rows.append({
            "id": next_id,
            "label": "",
            "source": "",
            "unit_divisor": 1,
            "default_category": "uncategorized",
            "categories": "",
        })
        return rows, "New tag added (unsaved)", True

    # ------------------------------------------------------------------ #
    # 18b. TAG MANAGER: Set source column for selected row
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("tm-def-table", "data", allow_duplicate=True),
            Output("tm-store-def-dirty", "data", allow_duplicate=True),
        ],
        Input("tm-source-dropdown", "value"),
        [
            State("tm-def-table", "data"),
            State("tm-def-table", "active_cell"),
        ],
        prevent_initial_call=True,
    )
    def on_set_source(source_val, rows, active_cell):
        if source_val is None or not active_cell or not rows:
            raise PreventUpdate
        idx = active_cell.get("row", -1)
        if 0 <= idx < len(rows):
            rows[idx]["source"] = source_val
            return rows, True
        raise PreventUpdate

    # ------------------------------------------------------------------ #
    # 18c. TAG MANAGER: Show source dropdown when source cell clicked
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("tm-source-row", "style"),
            Output("tm-source-dropdown", "value"),
        ],
        [
            Input("tm-def-table", "active_cell"),
            Input("tm-def-table", "selected_rows"),
        ],
        State("tm-def-table", "data"),
        prevent_initial_call=True,
    )
    def on_def_cell_selected(active_cell, selected, rows):
        show = active_cell and active_cell.get("column_id") == "source"
        if show and rows:
            row_idx = active_cell.get("row", -1)
            if 0 <= row_idx < len(rows):
                val = rows[row_idx].get("source", None) or None
                return {"display": "flex"}, val
        if show:
            return {"display": "flex"}, None
        return {"display": "none"}, None

    # ------------------------------------------------------------------ #
    # 19. TAG MANAGER: Remove Selected Tag definition
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("tm-def-table", "data", allow_duplicate=True),
            Output("tm-def-status", "children", allow_duplicate=True),
            Output("sm-tag-summary", "children", allow_duplicate=True),
            Output("tm-store-def-dirty", "data", allow_duplicate=True),
        ],
        Input("tm-btn-remove-def", "n_clicks"),
        [
            State("tm-def-table", "data"),
            State("tm-def-table", "selected_rows"),
            State("sm-series-dropdown", "value"),
        ],
        prevent_initial_call=True,
    )
    def on_remove_tag_def(n, rows, selected, series_name):
        if not n or not rows:
            raise PreventUpdate
        if not selected:
            return no_update, "Select a row first", no_update, no_update
        idx = selected[0]
        if 0 <= idx < len(rows):
            removed = rows.pop(idx)
            tag_id = removed.get("id")
            label = removed.get("label", idx)
            if tag_manager is not None and tag_id is not None:
                tag_manager.remove_tag_definition(tag_id)
                tag_manager.save()
                tag_manager.reload()
            summary = no_update
            if tag_manager is not None and series_name:
                scfg = tag_manager.get_series_config(series_name)
                defs = tag_manager.get_tag_definitions()
                names = [d["label"] for d in defs if str(d["id"]) in scfg]
                summary = ", ".join(names) if names else "(no tags defined for this series)"
            return rows, f"Removed tag '{label}' and its ranges.", summary, True
        return no_update, "Invalid selection", no_update, no_update

    # ------------------------------------------------------------------ #
    # 20. TAG MANAGER: Save Tag Definitions
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("tm-def-status", "children", allow_duplicate=True),
            Output("tm-tag-dropdown", "options"),
            Output("tm-tag-dropdown", "value"),
            Output("tm-store-def-dirty", "data", allow_duplicate=True),
        ],
        Input("tm-btn-save-defs", "n_clicks"),
        State("tm-def-table", "data"),
        prevent_initial_call=True,
    )
    def on_save_tag_defs(n, rows):
        if not n or tag_manager is None:
            raise PreventUpdate
        new_defs = []
        for r in rows:
            try:
                divisor = float(r.get("unit_divisor", 1))
            except (ValueError, TypeError):
                divisor = 1
            cats_raw = r.get("categories", "")
            cats = [c.strip() for c in cats_raw.split(",") if c.strip()]
            new_defs.append({
                "id": int(r["id"]),
                "label": r.get("label", ""),
                "source": r.get("source", ""),
                "unit_divisor": divisor,
                "default_category": r.get("default_category", "uncategorized"),
                "categories": cats,
            })
        tag_manager._definitions = new_defs
        tag_manager.save()
        tag_manager.reload()
        opts = [{"label": d["label"], "value": d["id"]}
                for d in tag_manager.get_tag_definitions()]
        val = opts[0]["value"] if opts else None
        return "Tag definitions saved.", opts, val, False

    # ------------------------------------------------------------------ #
    # 21. TAG MANAGER: Save Ranges for current series + tag
    # ------------------------------------------------------------------ #
    @app.callback(
        [
            Output("tm-save-status", "children"),
            Output("sm-tag-summary", "children", allow_duplicate=True),
            Output("tm-store-ranges-dirty", "data", allow_duplicate=True),
        ],
        Input("tm-btn-save-ranges", "n_clicks"),
        [
            State("sm-series-dropdown", "value"),
            State("tm-tag-dropdown", "value"),
            State("tm-range-table", "data"),
        ],
        prevent_initial_call=True,
    )
    def on_save_ranges(n, series_name, tag_id, range_rows):
        if not n or not series_name or tag_id is None or tag_manager is None:
            raise PreventUpdate
        ranges_dict = {}
        for row in range_rows:
            cat = row.get("category", "")
            raw = row.get("ranges", "").strip()
            pairs = []
            if raw:
                for part in raw.split(","):
                    part = part.strip()
                    for sep in ("\u2013", "--", "-"):
                        if sep in part:
                            tokens = part.split(sep, 1)
                            try:
                                lo = float(tokens[0].strip())
                                hi = float(tokens[1].strip())
                                pairs.append([lo, hi])
                            except (ValueError, IndexError):
                                pass
                            break
            ranges_dict[cat] = pairs
        tag_manager.set_series_ranges(series_name, tag_id, ranges_dict)
        tag_manager.save()
        scfg = tag_manager.get_series_config(series_name)
        defs = tag_manager.get_tag_definitions()
        tag_names = [d["label"] for d in defs if str(d["id"]) in scfg]
        summary = ", ".join(tag_names) if tag_names else "(no tags defined for this series)"
        return f"Ranges saved for {series_name}.", summary, False

    @app.callback(
        Output("tm-store-def-dirty", "data", allow_duplicate=True),
        Input("tm-def-table", "data_timestamp"),
        State("tm-def-table", "data_previous"),
        prevent_initial_call=True,
    )
    def on_tag_defs_table_edit(ts, prev):
        if ts is None:
            raise PreventUpdate
        if prev is None:
            raise PreventUpdate
        return True

    @app.callback(
        Output("tm-store-ranges-dirty", "data", allow_duplicate=True),
        Input("tm-range-table", "data_timestamp"),
        State("tm-range-table", "data_previous"),
        prevent_initial_call=True,
    )
    def on_ranges_table_edit(ts, prev):
        if ts is None:
            raise PreventUpdate
        if prev is None:
            raise PreventUpdate
        return True

    @app.callback(
        [
            Output("tm-btn-add-def", "color"),
            Output("tm-btn-save-defs", "color"),
            Output("tm-btn-save-defs", "disabled"),
            Output("tm-btn-remove-def", "color"),
            Output("tm-btn-remove-def", "disabled"),
            Output("tm-btn-save-ranges", "color"),
            Output("tm-btn-save-ranges", "disabled"),
        ],
        [
            Input("tm-store-def-dirty", "data"),
            Input("tm-store-ranges-dirty", "data"),
            Input("tm-def-table", "selected_rows"),
            Input("sm-series-dropdown", "value"),
            Input("tm-tag-dropdown", "value"),
            Input("tm-range-table", "data"),
        ],
        prevent_initial_call=False,
    )
    def set_tag_manager_button_states(def_dirty, ranges_dirty, selected_rows,
                                      series_name, tag_id, range_rows):
        # Definitions manager: one green at a time.
        if def_dirty:
            add_color = "dark"
            save_defs_color = "success"
            save_defs_disabled = False
        else:
            add_color = "success"
            save_defs_color = "secondary"
            save_defs_disabled = True

        has_selection = bool(selected_rows)
        remove_color = "danger" if has_selection else "secondary"
        remove_disabled = not has_selection

        # Ranges manager: gray when unavailable, green when unsaved changes exist.
        ranges_available = bool(series_name) and (tag_id is not None) and bool(range_rows)
        if not ranges_available:
            save_ranges_color = "secondary"
            save_ranges_disabled = True
        elif ranges_dirty:
            save_ranges_color = "success"
            save_ranges_disabled = False
        else:
            save_ranges_color = "secondary"
            save_ranges_disabled = True

        return (
            add_color,
            save_defs_color,
            save_defs_disabled,
            remove_color,
            remove_disabled,
            save_ranges_color,
            save_ranges_disabled,
        )


# â”€â”€ private helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _finalise_file_add(data_manager, series_name, bronze_path, tmp_path):
    """Add the imported file to the series definition and return outputs."""
    sdef = data_manager.series_defs.get(series_name, {})
    files = sdef.get("files", [])

    # Resolve bronze_path to absolute using the project root, so this works
    # regardless of the process working directory (e.g. on a remote workstation
    # where cwd is not the project root).
    project_root = data_manager._get_project_root()
    if not os.path.isabs(bronze_path):
        abs_bronze_path = os.path.normpath(os.path.join(project_root, bronze_path))
    else:
        abs_bronze_path = bronze_path

    # Prevent duplicate links of the same bronze asset within one series.
    normalized_new = os.path.normcase(os.path.normpath(abs_bronze_path))
    existing_idx = None
    for idx, fentry in enumerate(files):
        path_val = fentry.get("path")
        if not path_val:
            continue
        path_norm = path_val.replace('\\', '/')
        if not os.path.isabs(path_norm):
            abs_existing = os.path.normpath(os.path.join(project_root, path_norm))
        else:
            abs_existing = os.path.normpath(path_norm)
        if os.path.normcase(abs_existing) == normalized_new:
            existing_idx = idx
            break

    if existing_idx is not None:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        file_opts = _file_options(data_manager, series_name)
        return (file_opts, existing_idx, False, None,
                f"File '{os.path.basename(bronze_path)}' is already linked to this series.",
                "warning", True)

    # Read worksheet names
    ws_names = []
    try:
        # Use a context manager so the workbook handle is closed immediately;
        # otherwise Windows can keep the file locked for cleanup/delete.
        with pd.ExcelFile(abs_bronze_path) as xls:
            ws_names = xls.sheet_names
    except Exception:
        logger.warning("Could not read worksheets from '%s'.", abs_bronze_path)

    # Build worksheet dicts
    worksheet_dicts = [{"name": ws} for ws in ws_names]

    # --- Auto-detect headers for all worksheets ---
    for ws in worksheet_dicts:
        ws_name = ws.get("name")
        abs_path = abs_bronze_path
        try:
            from ..backend.data_loading import detect_header_and_data_row
            header_row, first_data_row, _ = detect_header_and_data_row(abs_path, worksheet=ws_name)
            if header_row is not None:
                ws["header_row"] = header_row
            if first_data_row is not None:
                ws["first_data_row"] = first_data_row
        except Exception:
            pass

    files.append({
        "path": bronze_path,
        "worksheets": worksheet_dicts,
    })
    sdef["files"] = files
    data_manager.series_defs[series_name] = sdef

    # Clean up temp file
    try:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except Exception:
        pass

    file_opts = _file_options(data_manager, series_name)
    new_val = len(files) - 1  # select newly added file
    return (file_opts, new_val, False, None,
            f"File '{os.path.basename(bronze_path)}' added.", "success", True)


def _update_ws_rows(dm, series_name, file_idx, ws_idx, header_row, first_data_row):
    """Persist header_row / first_data_row into the live series definition."""
    sdef = dm.series_defs.get(series_name, {})
    files = sdef.get("files", [])
    if file_idx is not None and 0 <= file_idx < len(files):
        wss = files[file_idx].get("worksheets", [])
        if ws_idx is not None and 0 <= ws_idx < len(wss):
            wss[ws_idx]["header_row"] = int(header_row)
            wss[ws_idx]["first_data_row"] = int(first_data_row)


def _build_style_conditions(mapping_data):
    """Build dash_table style_data_conditional list for colour-coded rows."""
    conditions = []
    for i, row in enumerate(mapping_data):
        origin = row.get("origin", "")
        file_col = row.get("file_column", "")
        if origin == "file" and not file_col:
            conditions.append({
                "if": {"row_index": i},
                "backgroundColor": "#ffcccc",
            })
        elif origin == "file" and file_col:
            conditions.append({
                "if": {"row_index": i},
                "backgroundColor": "#ccffcc",
            })
    return conditions

