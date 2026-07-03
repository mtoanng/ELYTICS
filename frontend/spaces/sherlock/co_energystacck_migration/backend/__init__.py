"""backend -- Backend package for the CO-stack reporting application.

Re-exports the public API surface that a frontend (Tkinter GUI or Dash app)
typically needs.  Import from the package directly::

    from src.backend import SeriesDataManager, parse_time_slicer, classify_columns
    from src.backend import plot_report, download_selected_data
"""

# --- Core manager ---
from .series_data_manager import (
    SeriesDataManager,
    parse_time_slicer,
    classify_columns,
)

# --- Visualization ---
from .data_visualization import (
    plot_report,
    save_report,
    save_html_report,
    save_and_open_report,
    get_base_parameter_names,
    strip_agg_suffix,
    add_agg_suffix,
    get_agg_columns_for_base,
)

# --- Data I/O ---
from .data_loading import (
    download_selected_data,
    detect_header_and_data_row,
    load_schema_columns,
)

# --- Enrichment ---
from .data_enrichment import (
    DataEnrichment,
    load_units_from_schema,
)

__all__ = [
    # Manager
    "SeriesDataManager",
    "parse_time_slicer",
    "classify_columns",
    # Visualization
    "plot_report",
    "save_report",
    "save_html_report",
    "save_and_open_report",
    "get_base_parameter_names",
    "strip_agg_suffix",
    "add_agg_suffix",
    "get_agg_columns_for_base",
    # Data I/O
    "download_selected_data",
    "detect_header_and_data_row",
    "load_schema_columns",
    # Enrichment
    "DataEnrichment",
    "load_units_from_schema",
]

