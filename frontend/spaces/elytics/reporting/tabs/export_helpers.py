"""Shared download and graph-export utilities for Elytics report tabs."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import dcc, html

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Shared diskcache for pending downloads (used by both tabs)
# ---------------------------------------------------------------------------
import diskcache

download_cache = diskcache.Cache(
    os.path.join(PROJECT_ROOT, ".dash_cache_downloads")
)


# ===================================================================== #
#  Save-modal layout factory                                             #
# ===================================================================== #

def build_save_modal(prefix: str) -> tuple:
    """Return ``(modal, download_component)`` wired to *prefix*-based IDs.

    Parameters
    ----------
    prefix : str
        Component-ID prefix, e.g. ``"custom"`` or ``"std"``.

    Returns
    -------
    tuple[dbc.Modal, dcc.Download]
        The modal component and the ``dcc.Download`` trigger.
    """
    modal = dbc.Modal(
        [
            dbc.ModalHeader("Save File", className="co-reporting-modal-header"),
            html.Div(
                id=f"div-{prefix}-modal-spinner-container",
                style={"position": "relative"},
                children=[
                    dbc.ModalBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Filename:", className="fw-bold"),
                                dbc.Input(
                                    id=f"input-{prefix}-save-filename",
                                    type="text",
                                    placeholder="Enter filename",
                                    className="mb-3",
                                ),
                            ]),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("File Type:", className="fw-bold"),
                                dcc.Dropdown(
                                    id=f"dd-{prefix}-save-filetype",
                                    options=[],
                                    clearable=False,
                                ),
                            ]),
                        ]),
                    ]),
                    html.Div(
                        id=f"div-{prefix}-modal-spinner",
                        style=_spinner_hidden_style(),
                        children=[dbc.Spinner(size="lg", color="primary")],
                    ),
                ],
            ),
            dbc.ModalFooter([
                dbc.Button("Cancel", id=f"btn-{prefix}-modal-cancel",
                           color="secondary"),
                dbc.Button("Save", id=f"btn-{prefix}-modal-save",
                           color="primary"),
            ], className="co-reporting-modal-footer"),
        ],
        id=f"modal-{prefix}-save",
        is_open=False,
        className="co-reporting-modal",
    )
    download = dcc.Download(id=f"download-{prefix}-file")
    return modal, download


# ===================================================================== #
#  Default-filename generators                                           #
# ===================================================================== #

def generate_default_download_filename(series_name: str) -> str:
    """Generate a default filename for data download (without extension)."""
    return f"download_{datetime.now().strftime('%y%m%d_%H%M%S')}"


def generate_default_graph_filename(series_name: str) -> str:
    """Generate a default filename for graph save (without extension)."""
    return f"{series_name}_custom_{datetime.now().strftime('%y%m%d_%H%M%S')}"


# ===================================================================== #
#  File-type option lists                                                #
# ===================================================================== #

def get_download_file_type_options() -> list[dict]:
    """Return file type options for data download modal."""
    return [
        {"label": "CSV (.csv)", "value": "csv"},
    ]


def get_graph_file_type_options() -> list[dict]:
    """Return file type options for graph save modal."""
    return [
        {"label": "HTML (.html)", "value": "html"},
    ]


# ===================================================================== #
#  Extension map                                                         #
# ===================================================================== #

EXT_MAP: dict[str, str] = {
    "csv": ".csv",
    "html": ".html",
}


# ===================================================================== #
#  Rangeslider / figure-dict cleanup for serialisation                   #
# ===================================================================== #

def clean_rangeslider_for_export(figure_dict: dict) -> None:
    """Remove non-schema keys from the rangeslider in *figure_dict* in-place.

    Plotly's ``Rangeslider`` schema only supports ``yaxis``, not ``yaxis2``,
    and ``_template`` keys cause serialisation failures.
    """
    layout = figure_dict.get("layout")
    if not isinstance(layout, dict):
        return
    xaxis = layout.get("xaxis")
    if not isinstance(xaxis, dict):
        return
    rangeslider = xaxis.get("rangeslider")
    if not isinstance(rangeslider, dict):
        return
    yaxis = rangeslider.get("yaxis")
    if isinstance(yaxis, dict):
        yaxis.pop("_template", None)
    rangeslider.pop("yaxis2", None)


# ===================================================================== #
#  Spinner style helpers                                                 #
# ===================================================================== #

_SPINNER_BASE: dict = {
    "position": "absolute",
    "top": "50%",
    "left": "50%",
    "transform": "translate(-50%, -50%)",
    "zIndex": "1000",
}


def _spinner_hidden_style() -> dict:
    """Return the CSS style dict for a hidden spinner overlay."""
    return {**_SPINNER_BASE, "display": "none"}


def spinner_style(is_saving: bool) -> dict:
    """Return the CSS style dict for the spinner based on *is_saving* state."""
    return {**_SPINNER_BASE, "display": "block" if is_saving else "none"}

