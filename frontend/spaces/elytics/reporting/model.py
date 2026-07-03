from __future__ import annotations

import re
from typing import Protocol

import pandas as pd

from .visualization import get_base_parameter_names


def classify_columns(df: pd.DataFrame):
    if df is None or df.empty:
        return [], []

    x_cols = []
    y_cols = []
    for column in df.columns:
        if column == "Elapsed time":
            continue
        if not (
            pd.api.types.is_float_dtype(df[column])
            or pd.api.types.is_numeric_dtype(df[column])
        ):
            continue
        lower_name = column.lower()
        if "date" in lower_name or "unnamed" in lower_name or "time" in lower_name:
            continue
        x_cols.append(column)
        y_cols.append(column)
    return get_base_parameter_names(x_cols), get_base_parameter_names(y_cols)


class SeriesDataManager(Protocol):
    series_defs: dict
    loaded_series: dict
    units: dict

    @staticmethod
    def _parse_agg_name(name: str) -> tuple[str, int | None]:
        match = re.match(r"^(.+)_agg(\d+)min$", name)
        if match:
            return match.group(1), int(match.group(2))
        return name, None

    def load_series_frame(self, series_name: str, force_reload: bool = False) -> pd.DataFrame: ...

    def unload_series(self, series_name: str) -> None: ...
