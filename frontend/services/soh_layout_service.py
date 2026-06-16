"""
Layout helpers and UI constants for the Sherlock SOH page.
"""

from __future__ import annotations

import pandas as pd


IS_RISING_OPTIONS = [
    {"label": "Both", "value": "both"},
    {"label": "Rising", "value": "rising"},
    {"label": "Falling", "value": "falling"},
]

COLOR_BY_OPTIONS = [
    {"label": "Anode Inlet Temperature (tAndeIn)", "value": "tAndeIn"},
    {"label": "Cathode Outlet Pressure (pCtdeOut)", "value": "pCtdeOut"},
    {"label": "Up/Down Pol Curve (is_rising)", "value": "is_rising"},
    {"label": "Fitting Error (model_min_obj_stack)", "value": "fitting_error_binned"},
]

X_AXIS_OPTIONS = [
    {"label": "Runtime [h]", "value": "runtime_hours"},
    {"label": "Timestamp", "value": "absolute_timestamp"},
]


def make_column_defs(df: pd.DataFrame) -> list[dict]:
    """Build AG Grid column definitions from dataframe dtypes."""
    col_defs: list[dict] = []
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            col_defs.append(
                {
                    "headerName": col,
                    "field": col,
                    "filter": True,
                    "sortable": True,
                    "resizable": True,
                    "minWidth": 90,
                    "flex": 1,
                    "type": "rightAligned",
                    "valueFormatter": {
                        "function": "params.value == null ? '' : Number(params.value).toFixed(3)"
                    },
                }
            )
        else:
            col_defs.append(
                {
                    "headerName": col,
                    "field": col,
                    "filter": True,
                    "sortable": True,
                    "resizable": True,
                    "minWidth": 120,
                    "flex": 1,
                }
            )
    return col_defs
