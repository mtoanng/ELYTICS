"""adls_files -- Dash tab for browsing and managing an ADLS Gen2 filesystem.

Treats the configured ADLS container as a virtual mounted filesystem.
The tab renders a familiar file-explorer UI with:

* Breadcrumb navigation for the current path.
* Action toolbar (Refresh, New folder, Upload, Rename, Copy, Delete).
* File table with checkbox selection, click-to-open for directories,
  click-to-download for files.
* Inline text preview / editor for small text files.
* Confirmation modals for destructive actions.

All filesystem operations go through :class:`ADLSFileSystem`.  When
ADLS is not configured (env vars unset) the tab shows a setup hint
instead of crashing.

Public API
----------
``layout(adls)``                 â†’ Dash component tree
``register_callbacks(app, adls)`` â†’ wires up all interactivity
"""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html, no_update, callback_context
from dash.dependencies import ALL, Input, Output, State
from dash.exceptions import PreventUpdate

from ..backend.adls_filesystem import (
    ADLSAlreadyExistsError,
    ADLSAuthError,
    ADLSConnectionTestResult,
    ADLSEntry,
    ADLSError,
    ADLSFileSystem,
    ADLSNetworkError,
    ADLSNotFoundError,
    ADLSPermissionDeniedError,
    _basename,
    _dirname,
    _join,
    _normalize,
)

logger = logging.getLogger(__name__)


# â”€â”€ constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


# Files larger than this are not previewed inline (forces download).
_PREVIEW_MAX_BYTES = 256 * 1024  # 256 KiB

# Text-file extensions eligible for inline preview / editing.
_TEXT_EXTS = {
    ".txt", ".csv", ".tsv", ".json", ".yaml", ".yml",
    ".md", ".log", ".py", ".js", ".html", ".xml", ".ini",
}


# â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _format_size(n: int) -> str:
    """Return a short human-readable byte count (``"1.4 MB"``)."""
    if not n:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _format_when(ts) -> str:
    """Format an SDK datetime as ``YYYY-MM-DD HH:MM`` (or ``""``)."""
    if not ts:
        return ""
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M")
    return str(ts)


def _is_text_file(name: str) -> bool:
    ext = os.path.splitext(name)[1].lower()
    return ext in _TEXT_EXTS


def _friendly_error(exc: BaseException, *, path: str = "") -> str:
    """Translate an ADLS* exception into a short actionable toast string.

    Falls back to ``str(exc)`` for any unmapped error so the user still
    gets some signal when an unexpected SDK exception slips through.
    """
    if isinstance(exc, ADLSAuthError):
        return "Service principal auth failed. Check ADLS_CLIENT_SECRET and tenant."
    if isinstance(exc, ADLSPermissionDeniedError):
        return (
            "Permission denied. The SP needs Storage Blob Data Contributor "
            "on the container."
        )
    if isinstance(exc, ADLSNotFoundError):
        return f"Not found: '{path or '?'}'."
    if isinstance(exc, ADLSAlreadyExistsError):
        return f"Already exists: '{path or '?'}'."
    if isinstance(exc, ADLSNetworkError):
        return (
            "Network error reaching ADLS. Check App Service outbound "
            "rules / proxy."
        )
    return str(exc)


# UI metadata for ADLSConnectionTestResult.kind values.
_TEST_HEADLINES = {
    "ok": "Connected",
    "not_configured": "Not configured",
    "auth_failed": "Auth failed \u2014 check service principal secret",
    "rbac_denied": (
        "RBAC denied \u2014 add Storage Blob Data Contributor on the "
        "storage account"
    ),
    "account_or_container_missing": "Container or account not found",
    "network_error": "Network error \u2014 check App Service outbound rules",
    "unknown": "Connection check failed",
}

_TEST_COLORS = {
    "ok": "success",
    "not_configured": "warning",
}


def _render_test_result(result: ADLSConnectionTestResult):
    """Render an :class:`ADLSConnectionTestResult` as a coloured ``dbc.Alert``.

    The alert uses an HTML ``<details>`` block for the redacted config
    summary and the raw SDK error string so neither floods the toolbar
    on success.  The SP secret is **never** rendered: the summary keys
    come from :meth:`ADLSFileSystem.config_summary`, which already
    redacts the secret to ``"***"`` or ``"(unset)"``.
    """
    color = _TEST_COLORS.get(result.kind, "danger")
    headline = _TEST_HEADLINES.get(result.kind, "Connection check failed")

    summary = result.summary or {}
    summary_lines = [f"{k}: {v}" for k, v in summary.items()]
    details_children = [
        html.Summary("Diagnostic details", className="small fw-bold"),
        html.Div(
            "Configuration:", className="small fw-bold mt-1",
        ),
        html.Pre(
            "\n".join(summary_lines) if summary_lines else "(no config available)",
            style={
                "whiteSpace": "pre-wrap",
                "wordBreak": "break-word",
                "fontSize": "0.78rem",
                "background": "rgba(0,0,0,0.04)",
                "border": "1px solid rgba(0,0,0,0.1)",
                "borderRadius": "4px",
                "padding": "6px",
                "marginBottom": "6px",
            },
        ),
    ]
    if result.sdk_error:
        details_children.extend(
            [
                html.Div("SDK error:", className="small fw-bold mt-1"),
                html.Pre(
                    result.sdk_error,
                    style={
                        "whiteSpace": "pre-wrap",
                        "wordBreak": "break-word",
                        "fontSize": "0.78rem",
                        "background": "rgba(0,0,0,0.04)",
                        "border": "1px solid rgba(0,0,0,0.1)",
                        "borderRadius": "4px",
                        "padding": "6px",
                    },
                ),
            ]
        )

    return dbc.Alert(
        [
            html.Div(headline, className="fw-bold"),
            html.Div(result.detail, className="small") if result.detail else html.Span(),
            html.Details(details_children, className="mt-2"),
        ],
        color=color,
        className="mb-2 py-2",
    )


def _build_breadcrumb(path: str) -> list:
    """Return a list of Dash components representing the breadcrumb."""
    parts = []
    parts.append(
        dbc.Button(
            "root",
            id={"type": "adls-crumb", "path": ""},
            color="link",
            size="sm",
            className="p-0",
            style={"textDecoration": "none"},
        )
    )
    if not path:
        return parts

    acc = ""
    for seg in path.split("/"):
        if not seg:
            continue
        acc = _join(acc, seg)
        parts.append(html.Span(" / ", className="text-muted small"))
        parts.append(
            dbc.Button(
                seg,
                id={"type": "adls-crumb", "path": acc},
                color="link",
                size="sm",
                className="p-0",
                style={"textDecoration": "none"},
            )
        )
    return parts


def _entries_to_rows(entries: list[ADLSEntry]) -> list[dict]:
    """Convert :class:`ADLSEntry` list to DataTable rows."""
    return [
        {
            "name": ("\U0001F4C1 " if e.is_dir else "\U0001F4C4 ") + e.name,
            "kind": "dir" if e.is_dir else "file",
            "size": _format_size(e.size),
            "modified": _format_when(e.last_modified),
            "path": e.path,
        }
        for e in entries
    ]


def _config_banner(adls: ADLSFileSystem):
    """Return a banner describing the current ADLS configuration."""
    cfg = adls.config_summary()
    if cfg["is_configured"]:
        return dbc.Alert(
            [
                html.Span("Connected: ", className="fw-bold"),
                html.Code(
                    f"{cfg['account_name']}/{cfg['container']}",
                    className="me-2",
                ),
                html.Span(
                    "(service principal auth)",
                    className="text-muted small",
                ),
            ],
            color="success",
            className="py-1 mb-2 small",
        )
    return dbc.Alert(
        [
            html.H6("ADLS not configured", className="alert-heading mb-1"),
            html.Div(
                [
                    "Set the following environment variables on the App Service "
                    "and restart:",
                    html.Br(),
                    html.Code(
                        "ADLS_ACCOUNT_NAME, ADLS_CONTAINER, ADLS_TENANT_ID, "
                        "ADLS_CLIENT_ID, ADLS_CLIENT_SECRET"
                    ),
                ],
                className="small",
            ),
        ],
        color="warning",
        className="mb-2",
    )


# â”€â”€ layout â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def layout(adls: ADLSFileSystem):
    """Return the Dash component tree for the ADLS Files tab."""

    return html.Div(
        style={
            "height": "100%",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "12px",
            "minHeight": "0",
        },
        children=[
            # ---- stores ----
            dcc.Store(id="adls-current-path", storage_type="memory", data=""),
            dcc.Store(id="adls-selected-paths", storage_type="memory", data=[]),
            dcc.Store(id="adls-refresh-trigger", storage_type="memory", data=0),

            # ---- browser-side file delivery ----
            dcc.Download(id="adls-download"),

            # ---- config / connection banner + Test connection button ----
            #
            # The Test connection button sits next to the banner (rather
            # than inside the action toolbar) so it stays clickable even
            # when ADLS is not configured.  The diagnostic alert below
            # only renders after the user clicks the button.
            dbc.Row(
                className="g-2 mb-1",
                align="center",
                children=[
                    dbc.Col(
                        html.Div(
                            id="adls-banner", children=_config_banner(adls)
                        ),
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Test connection",
                            id="adls-btn-test-connection",
                            color="info",
                            size="sm",
                            outline=True,
                        ),
                        width="auto",
                    ),
                ],
            ),
            html.Div(id="adls-test-result", className="mb-2"),

            # ---- toolbar ----
            dbc.Card(
                className="mb-2",
                children=dbc.CardBody(
                    className="py-2",
                    children=dbc.Row(
                        align="center",
                        children=[
                            dbc.Col(
                                width=7,
                                children=html.Div(
                                    id="adls-breadcrumb",
                                    children=_build_breadcrumb(""),
                                    style={
                                        "display": "flex",
                                        "flexWrap": "wrap",
                                        "alignItems": "center",
                                        "gap": "4px",
                                    },
                                ),
                            ),
                            dbc.Col(
                                width=5,
                                className="text-end",
                                children=dbc.ButtonGroup(
                                    size="sm",
                                    children=[
                                        dbc.Button(
                                            "Refresh",
                                            id="adls-btn-refresh",
                                            color="secondary",
                                            outline=True,
                                        ),
                                        dbc.Button(
                                            "New folder",
                                            id="adls-btn-new-folder",
                                            color="primary",
                                            outline=True,
                                        ),
                                        dbc.Button(
                                            "Upload",
                                            id="adls-btn-upload",
                                            color="primary",
                                            outline=True,
                                        ),
                                        dbc.Button(
                                            "Rename",
                                            id="adls-btn-rename",
                                            color="secondary",
                                            outline=True,
                                            disabled=True,
                                        ),
                                        dbc.Button(
                                            "Copy",
                                            id="adls-btn-copy",
                                            color="secondary",
                                            outline=True,
                                            disabled=True,
                                        ),
                                        dbc.Button(
                                            "Delete",
                                            id="adls-btn-delete",
                                            color="danger",
                                            outline=True,
                                            disabled=True,
                                        ),
                                    ],
                                ),
                            ),
                        ],
                    ),
                ),
            ),

            # ---- main content row: table on left, preview on right ----
            dbc.Row(
                className="flex-grow-1",
                style={"minHeight": "0", "overflow": "hidden"},
                children=[
                    # left: file table
                    dbc.Col(
                        width=7,
                        style={"height": "100%", "display": "flex", "flexDirection": "column"},
                        children=[
                            html.Div(
                                style={
                                    "flex": "1 1 auto",
                                    "minHeight": "0",
                                    "overflowY": "auto",
                                },
                                children=dash_table.DataTable(
                                    id="adls-table",
                                    columns=[
                                        {"name": "Name", "id": "name"},
                                        {"name": "Type", "id": "kind"},
                                        {"name": "Size", "id": "size"},
                                        {"name": "Modified", "id": "modified"},
                                    ],
                                    data=[],
                                    row_selectable="multi",
                                    selected_rows=[],
                                    style_cell={
                                        "fontSize": "0.85rem",
                                        "padding": "6px",
                                        "textAlign": "left",
                                    },
                                    style_header={
                                        "fontWeight": "600",
                                        "backgroundColor": "#f8f9fa",
                                    },
                                    style_data_conditional=[
                                        {
                                            "if": {"filter_query": '{kind} = "dir"'},
                                            "cursor": "pointer",
                                            "fontWeight": "500",
                                        },
                                    ],
                                    page_action="native",
                                    page_size=50,
                                    sort_action="native",
                                ),
                            ),
                        ],
                    ),
                    # right: preview / detail panel
                    dbc.Col(
                        width=5,
                        style={"height": "100%", "display": "flex", "flexDirection": "column"},
                        children=dbc.Card(
                            style={"height": "100%"},
                            children=[
                                dbc.CardHeader(
                                    id="adls-preview-header",
                                    className="py-2 small fw-bold",
                                    children="No file selected",
                                ),
                                dbc.CardBody(
                                    style={"overflowY": "auto", "minHeight": "0"},
                                    children=[
                                        html.Div(
                                            id="adls-preview-info",
                                            className="small text-muted mb-2",
                                        ),
                                        dbc.Button(
                                            "Download",
                                            id="adls-btn-download",
                                            color="primary",
                                            size="sm",
                                            disabled=True,
                                            className="mb-2",
                                        ),
                                        html.Div(id="adls-preview-body"),
                                    ],
                                ),
                            ],
                        ),
                    ),
                ],
            ),

            # ---- status bar ----
            html.Div(
                id="adls-status",
                className="small text-muted mt-2",
                children="Ready.",
            ),

            # ---- hidden upload component ----
            dcc.Upload(
                id="adls-upload",
                multiple=True,
                style={"display": "none"},
                children=html.Div(),
            ),

            # ---- modals ----
            _build_new_folder_modal(),
            _build_rename_modal(),
            _build_copy_modal(),
            _build_delete_modal(),
        ],
    )


def _build_new_folder_modal():
    return dbc.Modal(
        id="adls-modal-new-folder",
        is_open=False,
        children=[
            dbc.ModalHeader("Create new folder"),
            dbc.ModalBody(
                [
                    dbc.Label("Folder name", className="fw-bold small"),
                    dbc.Input(
                        id="adls-modal-new-folder-name",
                        placeholder="e.g. reports/2026",
                        type="text",
                    ),
                    html.Div(
                        "Slashes are allowed and create nested folders.",
                        className="text-muted small mt-1",
                    ),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(
                        "Cancel", id="adls-modal-new-folder-cancel", color="secondary"
                    ),
                    dbc.Button(
                        "Create", id="adls-modal-new-folder-ok", color="primary"
                    ),
                ]
            ),
        ],
    )


def _build_rename_modal():
    return dbc.Modal(
        id="adls-modal-rename",
        is_open=False,
        children=[
            dbc.ModalHeader("Rename / move"),
            dbc.ModalBody(
                [
                    dbc.Label("New path (relative to filesystem root)", className="fw-bold small"),
                    dbc.Input(id="adls-modal-rename-target", type="text"),
                    html.Div(
                        id="adls-modal-rename-hint",
                        className="text-muted small mt-1",
                    ),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(
                        "Cancel", id="adls-modal-rename-cancel", color="secondary"
                    ),
                    dbc.Button(
                        "Rename", id="adls-modal-rename-ok", color="primary"
                    ),
                ]
            ),
        ],
    )


def _build_copy_modal():
    return dbc.Modal(
        id="adls-modal-copy",
        is_open=False,
        children=[
            dbc.ModalHeader("Copy file"),
            dbc.ModalBody(
                [
                    dbc.Label("Destination path", className="fw-bold small"),
                    dbc.Input(id="adls-modal-copy-target", type="text"),
                    html.Div(
                        id="adls-modal-copy-hint",
                        className="text-muted small mt-1",
                    ),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button("Cancel", id="adls-modal-copy-cancel", color="secondary"),
                    dbc.Button("Copy", id="adls-modal-copy-ok", color="primary"),
                ]
            ),
        ],
    )


def _build_delete_modal():
    return dbc.Modal(
        id="adls-modal-delete",
        is_open=False,
        children=[
            dbc.ModalHeader("Confirm delete"),
            dbc.ModalBody(id="adls-modal-delete-body"),
            dbc.ModalFooter(
                [
                    dbc.Button(
                        "Cancel", id="adls-modal-delete-cancel", color="secondary"
                    ),
                    dbc.Button(
                        "Delete", id="adls-modal-delete-ok", color="danger"
                    ),
                ]
            ),
        ],
    )


# â”€â”€ callbacks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def register_callbacks(app, adls: ADLSFileSystem):
    """Wire up all interactivity for the ADLS Files tab."""

    # ------------------------------------------------------------------
    # 1) Listing: rebuild the table + breadcrumb whenever path or trigger changes
    # ------------------------------------------------------------------
    @app.callback(
        Output("adls-table", "data"),
        Output("adls-table", "selected_rows"),
        Output("adls-breadcrumb", "children"),
        Output("adls-status", "children", allow_duplicate=True),
        Input("adls-current-path", "data"),
        Input("adls-refresh-trigger", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def _refresh_listing(current_path, _trigger):
        path = _normalize(current_path)
        crumb = _build_breadcrumb(path)
        if not adls.is_configured():
            return [], [], crumb, "ADLS not configured."
        try:
            entries = adls.ls(path)
        except ADLSError as exc:
            return (
                [],
                [],
                crumb,
                f"Error listing '{path or '/'}': "
                + _friendly_error(exc, path=path or "/"),
            )
        rows = _entries_to_rows(entries)
        return rows, [], crumb, f"Listed {len(rows)} entry(ies) in '{path or '/'}'."

    # ------------------------------------------------------------------
    # 2) Breadcrumb click \u2192 navigate to that level
    # ------------------------------------------------------------------
    @app.callback(
        Output("adls-current-path", "data", allow_duplicate=True),
        Input({"type": "adls-crumb", "path": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def _crumb_clicked(n_clicks_list):
        if not any(n_clicks_list or []):
            raise PreventUpdate
        trig = callback_context.triggered_id
        if not isinstance(trig, dict):
            raise PreventUpdate
        return _normalize(trig.get("path", ""))

    # ------------------------------------------------------------------
    # 3) Table click on a directory row \u2192 navigate into it
    # ------------------------------------------------------------------
    @app.callback(
        Output("adls-current-path", "data", allow_duplicate=True),
        Input("adls-table", "active_cell"),
        State("adls-table", "data"),
        State("adls-current-path", "data"),
        prevent_initial_call=True,
    )
    def _navigate_into_dir(active_cell, rows, current_path):
        if not active_cell or not rows:
            raise PreventUpdate
        row_idx = active_cell.get("row")
        col_id = active_cell.get("column_id")
        if col_id != "name" or row_idx is None or row_idx >= len(rows):
            raise PreventUpdate
        row = rows[row_idx]
        if row.get("kind") != "dir":
            raise PreventUpdate
        return _normalize(row.get("path", ""))

    # ------------------------------------------------------------------
    # 4) Track selection \u2192 enable/disable toolbar buttons + preview
    # ------------------------------------------------------------------
    @app.callback(
        Output("adls-selected-paths", "data"),
        Output("adls-btn-rename", "disabled"),
        Output("adls-btn-copy", "disabled"),
        Output("adls-btn-delete", "disabled"),
        Output("adls-btn-download", "disabled"),
        Output("adls-preview-header", "children"),
        Output("adls-preview-info", "children"),
        Output("adls-preview-body", "children"),
        Input("adls-table", "selected_rows"),
        State("adls-table", "data"),
    )
    def _on_selection(selected_rows, rows):
        sel = selected_rows or []
        if not sel or not rows:
            return [], True, True, True, True, "No file selected", "", ""

        selected_paths = [rows[i]["path"] for i in sel if i < len(rows)]
        selected_entries = [rows[i] for i in sel if i < len(rows)]
        single = len(selected_entries) == 1
        only_files = all(r["kind"] == "file" for r in selected_entries)

        # toolbar buttons:
        # - Rename: single item (dir or file)
        # - Copy:   single FILE only (dirs not supported by ADLS SDK)
        # - Delete: any selection
        # - Download: single FILE only
        rename_dis = not single
        copy_dis = not (single and selected_entries[0]["kind"] == "file")
        delete_dis = False
        download_dis = not (single and selected_entries[0]["kind"] == "file")

        # build preview pane
        if not single:
            header = f"{len(selected_entries)} items selected"
            info = ", ".join(p["name"] for p in selected_entries[:6]) + (
                ", ..." if len(selected_entries) > 6 else ""
            )
            body = ""
        else:
            row = selected_entries[0]
            header = row["name"]
            info_bits = [
                f"Path: {row['path']}",
                f"Type: {row['kind']}",
            ]
            if row["size"]:
                info_bits.append(f"Size: {row['size']}")
            if row["modified"]:
                info_bits.append(f"Modified: {row['modified']}")
            info = html.Div([html.Div(b) for b in info_bits])
            body = _maybe_preview(adls, row)

        return (
            selected_paths,
            rename_dis,
            copy_dis,
            delete_dis,
            download_dis,
            header,
            info,
            body,
        )

    # ------------------------------------------------------------------
    # 5) Refresh button
    # ------------------------------------------------------------------
    @app.callback(
        Output("adls-refresh-trigger", "data", allow_duplicate=True),
        Input("adls-btn-refresh", "n_clicks"),
        State("adls-refresh-trigger", "data"),
        prevent_initial_call=True,
    )
    def _refresh(_n, tick):
        return (tick or 0) + 1

    # ------------------------------------------------------------------
    # 5a) Test connection button \u2192 probe ADLS and render diagnostic
    # ------------------------------------------------------------------
    @app.callback(
        Output("adls-test-result", "children"),
        Output("adls-status", "children", allow_duplicate=True),
        Input("adls-btn-test-connection", "n_clicks"),
        prevent_initial_call=True,
    )
    def _test_connection(_n):
        # ``test_connection`` never raises; the result struct already
        # carries everything the alert needs.
        result = adls.test_connection()
        return _render_test_result(result), f"Connection test: {result.kind}"

    # ------------------------------------------------------------------
    # 6) Download button \u2192 stream file to browser
    # ------------------------------------------------------------------
    @app.callback(
        Output("adls-download", "data"),
        Output("adls-status", "children", allow_duplicate=True),
        Input("adls-btn-download", "n_clicks"),
        State("adls-selected-paths", "data"),
        prevent_initial_call=True,
    )
    def _download(_n, selected_paths):
        if not selected_paths or len(selected_paths) != 1:
            return no_update, "Select exactly one file to download."
        path = selected_paths[0]
        try:
            data = adls.read_bytes(path)
        except ADLSError as exc:
            return no_update, f"Download error: {_friendly_error(exc, path=path)}"
        return (
            dict(
                content=base64.b64encode(data).decode("ascii"),
                filename=_basename(path),
                base64=True,
            ),
            f"Downloaded {_basename(path)} ({_format_size(len(data))}).",
        )

    # ------------------------------------------------------------------
    # 7) New folder
    # ------------------------------------------------------------------
    @app.callback(
        Output("adls-modal-new-folder", "is_open"),
        Output("adls-modal-new-folder-name", "value"),
        Input("adls-btn-new-folder", "n_clicks"),
        Input("adls-modal-new-folder-cancel", "n_clicks"),
        Input("adls-modal-new-folder-ok", "n_clicks"),
        State("adls-modal-new-folder", "is_open"),
        prevent_initial_call=True,
    )
    def _toggle_new_folder_modal(_open, _cancel, _ok, is_open):
        trig = callback_context.triggered_id
        if trig == "adls-btn-new-folder":
            return True, ""
        return False, ""

    @app.callback(
        Output("adls-refresh-trigger", "data", allow_duplicate=True),
        Output("adls-status", "children", allow_duplicate=True),
        Input("adls-modal-new-folder-ok", "n_clicks"),
        State("adls-modal-new-folder-name", "value"),
        State("adls-current-path", "data"),
        State("adls-refresh-trigger", "data"),
        prevent_initial_call=True,
    )
    def _do_new_folder(_n, name, current_path, tick):
        if not name:
            return no_update, "Folder name is empty."
        target = _join(current_path or "", name)
        try:
            adls.mkdir(target, exist_ok=False)
        except ADLSError as exc:
            return no_update, f"Create folder failed: {_friendly_error(exc, path=target)}"
        return (tick or 0) + 1, f"Created folder: {target}"

    # ------------------------------------------------------------------
    # 8) Upload
    # ------------------------------------------------------------------
    @app.callback(
        Output("adls-upload", "contents"),
        Input("adls-btn-upload", "n_clicks"),
        prevent_initial_call=True,
    )
    def _open_upload_dialog(_n):
        # Resetting contents to None lets the user pick the same file twice.
        return None

    app.clientside_callback(
        # Programmatically click the hidden dcc.Upload input when the
        # toolbar "Upload" button is pressed.
        """
        function(n_clicks) {
            if (!n_clicks) { return window.dash_clientside.no_update; }
            var el = document.getElementById('adls-upload');
            if (!el) { return window.dash_clientside.no_update; }
            var input = el.querySelector('input[type="file"]');
            if (input) { input.click(); }
            return window.dash_clientside.no_update;
        }
        """,
        Output("adls-btn-upload", "n_clicks"),
        Input("adls-btn-upload", "n_clicks"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("adls-refresh-trigger", "data", allow_duplicate=True),
        Output("adls-status", "children", allow_duplicate=True),
        Input("adls-upload", "contents"),
        State("adls-upload", "filename"),
        State("adls-current-path", "data"),
        State("adls-refresh-trigger", "data"),
        prevent_initial_call=True,
    )
    def _do_upload(contents_list, names_list, current_path, tick):
        if not contents_list:
            raise PreventUpdate
        if not isinstance(contents_list, list):
            contents_list = [contents_list]
            names_list = [names_list]

        ok = 0
        errors = []
        for content, name in zip(contents_list, names_list or []):
            if not content or not name:
                continue
            target = _join(current_path or "", name)
            try:
                _header, b64 = content.split(",", 1)
                data = base64.b64decode(b64)
                adls.write_bytes(target, data, overwrite=True)
                ok += 1
            except ADLSError as exc:
                errors.append(f"{name}: {_friendly_error(exc, path=target)}")
            except Exception as exc:  # noqa: BLE001 (surface to UI)
                errors.append(f"{name}: {exc}")

        msg = f"Uploaded {ok} file(s)." if ok else "No files uploaded."
        if errors:
            msg += "  Errors: " + "; ".join(errors[:3])
        return (tick or 0) + 1, msg

    # ------------------------------------------------------------------
    # 9) Rename
    # ------------------------------------------------------------------
    @app.callback(
        Output("adls-modal-rename", "is_open"),
        Output("adls-modal-rename-target", "value"),
        Output("adls-modal-rename-hint", "children"),
        Input("adls-btn-rename", "n_clicks"),
        Input("adls-modal-rename-cancel", "n_clicks"),
        Input("adls-modal-rename-ok", "n_clicks"),
        State("adls-selected-paths", "data"),
        prevent_initial_call=True,
    )
    def _toggle_rename_modal(_open, _cancel, _ok, selected_paths):
        trig = callback_context.triggered_id
        if trig != "adls-btn-rename":
            return False, "", ""
        if not selected_paths or len(selected_paths) != 1:
            return False, "", ""
        src = selected_paths[0]
        return True, src, f"Renaming '{src}' (must remain inside the filesystem)."

    @app.callback(
        Output("adls-refresh-trigger", "data", allow_duplicate=True),
        Output("adls-status", "children", allow_duplicate=True),
        Input("adls-modal-rename-ok", "n_clicks"),
        State("adls-modal-rename-target", "value"),
        State("adls-selected-paths", "data"),
        State("adls-refresh-trigger", "data"),
        prevent_initial_call=True,
    )
    def _do_rename(_n, target, selected_paths, tick):
        if not target or not selected_paths or len(selected_paths) != 1:
            return no_update, "Rename: nothing to do."
        src = selected_paths[0]
        try:
            adls.rename(src, target)
        except ADLSError as exc:
            return (
                no_update,
                f"Rename failed: {_friendly_error(exc, path=src)}",
            )
        return (tick or 0) + 1, f"Renamed '{src}' \u2192 '{_normalize(target)}'."

    # ------------------------------------------------------------------
    # 10) Copy
    # ------------------------------------------------------------------
    @app.callback(
        Output("adls-modal-copy", "is_open"),
        Output("adls-modal-copy-target", "value"),
        Output("adls-modal-copy-hint", "children"),
        Input("adls-btn-copy", "n_clicks"),
        Input("adls-modal-copy-cancel", "n_clicks"),
        Input("adls-modal-copy-ok", "n_clicks"),
        State("adls-selected-paths", "data"),
        prevent_initial_call=True,
    )
    def _toggle_copy_modal(_open, _cancel, _ok, selected_paths):
        trig = callback_context.triggered_id
        if trig != "adls-btn-copy":
            return False, "", ""
        if not selected_paths or len(selected_paths) != 1:
            return False, "", ""
        src = selected_paths[0]
        base, ext = os.path.splitext(_basename(src))
        suggested = _join(_dirname(src), f"{base}_copy{ext}")
        return True, suggested, f"Copying '{src}'. Server-side roundtrip; large files may be slow."

    @app.callback(
        Output("adls-refresh-trigger", "data", allow_duplicate=True),
        Output("adls-status", "children", allow_duplicate=True),
        Input("adls-modal-copy-ok", "n_clicks"),
        State("adls-modal-copy-target", "value"),
        State("adls-selected-paths", "data"),
        State("adls-refresh-trigger", "data"),
        prevent_initial_call=True,
    )
    def _do_copy(_n, target, selected_paths, tick):
        if not target or not selected_paths or len(selected_paths) != 1:
            return no_update, "Copy: nothing to do."
        src = selected_paths[0]
        try:
            adls.copy(src, target)
        except ADLSError as exc:
            return (
                no_update,
                f"Copy failed: {_friendly_error(exc, path=src)}",
            )
        return (tick or 0) + 1, f"Copied '{src}' \u2192 '{_normalize(target)}'."

    # ------------------------------------------------------------------
    # 11) Delete
    # ------------------------------------------------------------------
    @app.callback(
        Output("adls-modal-delete", "is_open"),
        Output("adls-modal-delete-body", "children"),
        Input("adls-btn-delete", "n_clicks"),
        Input("adls-modal-delete-cancel", "n_clicks"),
        Input("adls-modal-delete-ok", "n_clicks"),
        State("adls-selected-paths", "data"),
        State("adls-table", "data"),
        prevent_initial_call=True,
    )
    def _toggle_delete_modal(_open, _cancel, _ok, selected_paths, rows):
        trig = callback_context.triggered_id
        if trig != "adls-btn-delete":
            return False, ""
        if not selected_paths:
            return False, ""
        names = [_basename(p) for p in selected_paths]
        preview = "\n".join(f"\u2022 {n}" for n in names[:8])
        if len(names) > 8:
            preview += f"\n\u2026 and {len(names) - 8} more"
        return True, html.Pre(
            f"Permanently delete the following {len(names)} item(s)?\n\n{preview}",
            style={"whiteSpace": "pre-wrap", "fontSize": "0.85rem"},
        )

    @app.callback(
        Output("adls-refresh-trigger", "data", allow_duplicate=True),
        Output("adls-status", "children", allow_duplicate=True),
        Input("adls-modal-delete-ok", "n_clicks"),
        State("adls-selected-paths", "data"),
        State("adls-table", "data"),
        State("adls-refresh-trigger", "data"),
        prevent_initial_call=True,
    )
    def _do_delete(_n, selected_paths, rows, tick):
        if not selected_paths:
            return no_update, "Delete: nothing selected."
        kinds = {r["path"]: r["kind"] for r in (rows or [])}
        ok = 0
        errors = []
        for p in selected_paths:
            try:
                if kinds.get(p) == "dir":
                    adls.rmdir(p, recursive=True)
                else:
                    adls.rm(p)
                ok += 1
            except ADLSError as exc:
                errors.append(f"{_basename(p)}: {_friendly_error(exc, path=p)}")
        msg = f"Deleted {ok} item(s)."
        if errors:
            msg += "  Errors: " + "; ".join(errors[:3])
        return (tick or 0) + 1, msg


# â”€â”€ preview helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _maybe_preview(adls: ADLSFileSystem, row: dict):
    """Return a Dash component previewing *row*, or an empty string."""
    if row.get("kind") != "file":
        return ""
    path = row.get("path", "")
    if not path:
        return ""

    name = _basename(path)
    if not _is_text_file(name):
        return html.Div(
            "Binary file â€“ use Download to retrieve.",
            className="text-muted small fst-italic",
        )

    try:
        entry = adls.stat(path)
    except ADLSError as exc:
        return html.Div(
            f"Preview error: {_friendly_error(exc, path=path)}",
            className="text-danger small",
        )

    if entry.size > _PREVIEW_MAX_BYTES:
        return html.Div(
            f"File too large to preview ({_format_size(entry.size)}). "
            "Use Download.",
            className="text-muted small fst-italic",
        )

    try:
        text = adls.read_text(path)
    except ADLSError as exc:
        return html.Div(
            f"Preview error: {_friendly_error(exc, path=path)}",
            className="text-danger small",
        )

    return html.Pre(
        text,
        style={
            "whiteSpace": "pre-wrap",
            "wordBreak": "break-word",
            "fontSize": "0.8rem",
            "background": "#f8f9fa",
            "border": "1px solid #dee2e6",
            "borderRadius": "4px",
            "padding": "8px",
            "maxHeight": "100%",
            "overflow": "auto",
        },
    )

