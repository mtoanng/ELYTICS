"""export_helpers -- Shared download / graph-export utilities for report tabs.

Consolidates the save-modal layout, file dialog helpers, figure-to-image
conversion, and the shared ``diskcache`` instance so that both Standard
Reports and Custom Reports stay DRY.

Functions
---------
Layout           : ``build_save_modal``
Filename helpers : ``generate_default_download_filename``,
                   ``generate_default_graph_filename``
File-type lists  : ``get_download_file_type_options``,
                   ``get_graph_file_type_options``
Figure export    : ``clean_rangeslider_for_export``,
                   ``strip_private_keys``,
                   ``prepare_figure_for_image_export``,
                   ``figure_to_image_bytes``,
                   ``png_to_pdf_bytes``
Spinner helpers  : ``spinner_style``
"""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime

import dash_bootstrap_components as dbc
import plotly.io as pio
from dash import dcc, html

from ..backend.project_root import PROJECT_ROOT

# Lazy-imported on first use (reportlab / PIL may be absent in slim envs)
_reportlab_available: bool | None = None

# ---------------------------------------------------------------------------
# Shared diskcache for pending downloads (used by both tabs)
# ---------------------------------------------------------------------------
import os
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
        {"label": "PNG (.png)", "value": "png"},
        {"label": "PDF (.pdf)", "value": "pdf"},
        {"label": "JPEG (.jpg)", "value": "jpg"},
    ]


# ===================================================================== #
#  Extension map                                                         #
# ===================================================================== #

EXT_MAP: dict[str, str] = {
    "csv": ".csv",
    "html": ".html",
    "png": ".png",
    "pdf": ".pdf",
    "jpg": ".jpg",
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


def strip_private_keys(obj):
    """Recursively remove keys that start with ``_`` from nested dicts/lists."""
    if isinstance(obj, dict):
        return {k: strip_private_keys(v) for k, v in obj.items()
                if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_private_keys(i) for i in obj]
    return obj


def prepare_figure_for_image_export(figure_dict: dict, series_name: str,
                                    resolution_label_str: str,
                                    report_name: str = "") -> "go.Figure":
    """Reconstruct a Plotly ``Figure`` from *figure_dict* ready for raster export.

    * Strips private Plotly keys (``_template``, etc.)
    * Disables the rangeslider (irrelevant for static images)
    * Adds a centred title when none is present

    Returns the reconstructed ``Figure``.
    """
    fig_dict_clean = strip_private_keys(figure_dict)
    layout = fig_dict_clean.get("layout", {})
    xaxis = layout.get("xaxis")
    if isinstance(xaxis, dict):
        xaxis["rangeslider"] = {"visible": False}

    fig = pio.from_json(json.dumps(fig_dict_clean))
    fig.update_xaxes(rangeslider_visible=False)

    img_title = (
        f"{series_name}  \u2014 {report_name}  [{resolution_label_str}]"
        if report_name
        else f"{series_name}  [{resolution_label_str}]"
    )
    if not (fig.layout.title and fig.layout.title.text):
        fig.update_layout(
            title=dict(text=img_title, x=0.5, xanchor="center")
        )
    return fig, img_title


def figure_to_image_bytes(fig, fmt: str = "png",
                          width: int = 1600, height: int = 900,
                          scale: int = 2) -> bytes:
    """Render a Plotly figure to raster bytes via ``kaleido``.

    Parameters
    ----------
    fig : plotly.graph_objs.Figure
    fmt : str
        Image format (``"png"``, ``"jpeg"``, ``"pdf"``).
    width, height, scale : int
        Output dimensions.

    Returns
    -------
    bytes
        Raw image data.
    """
    return pio.to_image(fig, format=fmt, width=width, height=height, scale=scale)


# ===================================================================== #
#  PNG â†’ PDF conversion                                                  #
# ===================================================================== #

def png_to_pdf_bytes(png_bytes: bytes, title: str = "") -> bytes:
    """Embed PNG image data into a landscape-A4 PDF using *reportlab*.

    Parameters
    ----------
    png_bytes : bytes
        Raw PNG image data (e.g. from ``pio.to_image``).
    title : str
        Optional title drawn above the graph.

    Returns
    -------
    bytes
        Raw PDF bytes suitable for base64 encoding and download.

    Raises
    ------
    RuntimeError
        If image processing or PDF generation fails.
    """
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(png_bytes))
        img_width, img_height = img.size

        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=landscape(A4))
        page_width, page_height = landscape(A4)

        scale = min(page_width / img_width, page_height / img_height) * 0.95
        new_width = img_width * scale
        new_height = img_height * scale

        x = (page_width - new_width) / 2
        y = (page_height - new_height) / 2

        if title:
            c.setFont("Helvetica", 12)
            c.drawString(50, page_height - 30, title)
            y -= 40

        img_reader = ImageReader(io.BytesIO(png_bytes))
        c.drawImage(image=img_reader, x=x, y=y,
                    width=new_width, height=new_height)

        c.save()
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()

    except Exception as e:
        raise RuntimeError(f"PNG-to-PDF conversion failed: {e}") from e


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

