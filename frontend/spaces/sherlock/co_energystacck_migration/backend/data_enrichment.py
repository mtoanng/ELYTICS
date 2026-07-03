"""data_enrichment -- Calculated columns, aggregation, and plausibility limits.

This module owns every *derived* column that does not exist in the raw data:

* Energy Efficiency, Current Density, Delta-p Anolyte, Single Pass Conversion
  Efficiency -- each as a static method with column-existence guards.
* ``aggregate_timeseries()`` -- time-bin aggregation producing
  ``_min`` / ``_max`` / ``_mean`` triplets.
* ``apply_plausibility_limits()`` -- clips columns whose schema unit is ``%``
  to [0, 100].
* ``load_units_from_schema()`` -- helper that builds a ``{column: unit}`` dict
  from ``data/schema.csv``.

The ``DataEnrichment`` class uses a pluggable *enabled_steps* list so callers
can opt in/out of individual enrichment steps.  The default pipeline is::

    add_energy_efficiency -> add_delta_p_anolyte -> add_current_density
    -> add_single_pass_conversion_efficiency -> apply_plausibility_limits

``add_units_to_column_names`` and ``add_time_in_hours`` are available but
**not** enabled by default.
"""

import pandas as pd
import numpy as np
import os

from . import paths
from .data_loading import _read_csv_with_bom_fix

# ``SCHEMA_PATH`` is intentionally re-exported from this module for the
# handful of callers that ``from data_enrichment import SCHEMA_PATH``;
# the canonical value lives in ``src.backend.paths``.
SCHEMA_PATH = paths.SCHEMA_PATH


def load_units_from_schema(schema_path=None):
    """Load a dict of {column_name: unit} from the schema CSV.

    When *schema_path* is ``None`` (the default) the canonical read-only
    location from :mod:`src.backend.paths` is used. Callers that want to
    point at a custom schema (tests, alternative deployments) can still
    pass an explicit path.
    """
    if schema_path is None:
        schema_path = paths.SCHEMA_PATH
    units = {}
    if not os.path.exists(schema_path):
        return units
    for row in _read_csv_with_bom_fix(schema_path):
        name = row.get("name", "").strip()
        unit = row.get("unit", "").strip()
        if name and unit:
            units[name] = unit
    return units


class DataEnrichment:
    def __init__(self, enabled_steps=None, active_area=88.0):
        """
        enabled_steps: list of enrichment step names to apply (default: all except
                       add_units_to_column_names which is available but opt-in).
        active_area: float, used for current density calculation
        """
        self.active_area = active_area
        self.enabled_steps = enabled_steps or [
            "add_energy_efficiency",
            "add_delta_p_anolyte",
            "add_current_density",
            "add_faradaic_efficiency_co_h2",
            "add_flow_rate_co_out",
            "add_flow_rate_h2_out",
            "add_flow_rate_o2_out",
            "add_flow_rate_co2_out",
            "add_flow_rate_co2_out_anode",
            "add_flow_rate_co2_out_cathode",
            "add_ratio_co_h2",
            "add_single_pass_conversion_efficiency",
            "apply_plausibility_limits",
        ]

    def enrich(self, df: pd.DataFrame, mapping=None, units=None) -> pd.DataFrame:
        """
        Apply enabled enrichment steps to the DataFrame.

        Args:
            df:      Input DataFrame.
            mapping: Mapping list (currently unused, reserved for future use).
            units:   Optional dict of {column_name: unit} from schema.
                     If None, loaded from schema CSV (fallback).
        """
        df = df.copy()
        if units is None:
            units = load_units_from_schema()
        for step in self.enabled_steps:
            if step == "add_units_to_column_names":
                df = self.add_units_to_column_names(df, units)
            elif step == "add_time_in_hours":
                df = self.add_time_in_hours(df)
            elif step == "add_energy_efficiency":
                df = self.add_energy_efficiency(df)
            elif step == "add_delta_p_anolyte":
                df = self.add_delta_p_anolyte(df)
            elif step == "add_current_density":
                df = self.add_current_density(df, self.active_area)
            elif step == "add_faradaic_efficiency_co_h2":
                df = self.add_faradaic_efficiency_co_h2(df)
            elif step == "add_flow_rate_co_out":
                df = self.add_flow_rate_co_out(df)
            elif step == "add_flow_rate_h2_out":
                df = self.add_flow_rate_h2_out(df)
            elif step == "add_flow_rate_o2_out":
                df = self.add_flow_rate_o2_out(df)
            elif step == "add_flow_rate_co2_out":
                df = self.add_flow_rate_co2_out(df)
            elif step == "add_flow_rate_co2_out_anode":
                df = self.add_flow_rate_co2_out_anode(df)
            elif step == "add_flow_rate_co2_out_cathode":
                df = self.add_flow_rate_co2_out_cathode(df)
            elif step == "add_ratio_co_h2":
                df = self.add_ratio_co_h2(df)
            elif step == "add_single_pass_conversion_efficiency":
                df = self.add_single_pass_conversion_efficiency(df)
            elif step == "apply_plausibility_limits":
                df = self.apply_plausibility_limits(df, units)
        return df

    @staticmethod
    def add_units_to_column_names(df: pd.DataFrame, units: dict) -> pd.DataFrame:
        """Rename columns by appending unit from schema. Must run last."""
        df = df.copy()
        new_columns = {}
        for col in df.columns:
            unit = units.get(col)
            if unit and f"[{unit}]" not in col:
                new_columns[col] = f"{col} [{unit}]"
            else:
                new_columns[col] = col
        df.rename(columns=new_columns, inplace=True)
        return df

    @staticmethod
    def add_time_in_hours(df: pd.DataFrame) -> pd.DataFrame:
        if "Elapsed time" not in df.columns:
            return df
        df = df.copy()
        df["Time"] = pd.to_numeric(df["Elapsed time"], errors="coerce") / 3600.0
        return df

    @staticmethod
    def add_energy_efficiency(df: pd.DataFrame) -> pd.DataFrame:
        required = ["Faradaic Efficiency of CO", "Stack Voltage"]
        if not all(col in df.columns for col in required):
            return df
        df = df.copy()
        fe = pd.to_numeric(df["Faradaic Efficiency of CO"], errors="coerce")
        stack_voltage = pd.to_numeric(df["Stack Voltage"], errors="coerce")
        ee = 1.48 * fe / (stack_voltage / 5)
        ee = ee.replace([float("inf"), float("-inf")], pd.NA)
        df["Energy Efficiency"] = pd.to_numeric(ee, errors="coerce")
        df["Energy Efficiency"] = df["Energy Efficiency"].replace(
            [np.inf, -np.inf], np.nan
        )
        return df

    @staticmethod
    def add_delta_p_anolyte(df: pd.DataFrame) -> pd.DataFrame:
        required = ["Anolyte inlet pressure", "Anolyte outlet pressure"]
        if not all(col in df.columns for col in required):
            return df
        df = df.copy()
        inlet = pd.to_numeric(df["Anolyte inlet pressure"], errors="coerce")
        outlet = pd.to_numeric(df["Anolyte outlet pressure"], errors="coerce")
        df["Î”p Anolyte"] = inlet - outlet
        df["Î”p Anolyte"] = df["Î”p Anolyte"].replace([np.inf, -np.inf], np.nan)
        return df

    @staticmethod
    def add_current_density(
        df: pd.DataFrame, active_area: float = 88.0
    ) -> pd.DataFrame:
        if "Current" not in df.columns:
            return df
        df = df.copy()
        current = pd.to_numeric(df["Current"], errors="coerce")
        df["Current density"] = 1000 * current / active_area
        df["Current density"] = df["Current density"].replace([np.inf, -np.inf], np.nan)
        return df

    @staticmethod
    def add_flow_rate_co_out(df: pd.DataFrame) -> pd.DataFrame:
        required = ["Faradaic Efficiency of CO", "Current"]
        if not all(col in df.columns for col in required):
            return df
        df = df.copy()
        FECO = pd.to_numeric(df["Faradaic Efficiency of CO"], errors="coerce") / 100
        I = pd.to_numeric(df["Current"], errors="coerce")
        F = 96485.3  # Faraday's constant in C/mol
        Vm = 22.414  # l/mol at STP
        df["Flow CO out"] = ((FECO * I) / (2 * F)) * (
            Vm * 60
        )  # convert to nlpm for the whole stack
        df["Flow CO out"] = df["Flow CO out"].replace([np.inf, -np.inf], np.nan)
        return df

    @staticmethod
    def add_flow_rate_h2_out(df: pd.DataFrame) -> pd.DataFrame:
        required = ["Faradaic Efficiency of H2", "Current"]
        if not all(col in df.columns for col in required):
            return df
        df = df.copy()
        FEH2 = pd.to_numeric(df["Faradaic Efficiency of H2"], errors="coerce") / 100
        I = pd.to_numeric(df["Current"], errors="coerce")
        F = 96485.3  # Faraday's constant in C/mol
        Vm = 22.414  # l/mol at STP
        df["Flow H2 out"] = ((FEH2 * I) / (2 * F)) * (
            Vm * 60
        )  # convert to nlpm for the whole stack
        df["Flow H2 out"] = df["Flow H2 out"].replace([np.inf, -np.inf], np.nan)
        return df

    @staticmethod
    def add_flow_rate_o2_out(df: pd.DataFrame) -> pd.DataFrame:
        required = ["Faradaic Efficiency of O2", "Current"]
        if not all(col in df.columns for col in required):
            return df
        df = df.copy()
        FEO2 = pd.to_numeric(df["Faradaic Efficiency of O2"], errors="coerce") / 100
        I = pd.to_numeric(df["Current"], errors="coerce")
        F = 96485.3  # Faraday's constant in C/mol
        Vm = 22.414  # l/mol at STP
        df["Flow O2 out"] = ((FEO2 * I) / (4 * F)) * (
            Vm * 60
        )  # convert to nlpm for the whole stack
        df["Flow O2 out"] = df["Flow O2 out"].replace([np.inf, -np.inf], np.nan)
        return df

    @staticmethod
    def add_flow_rate_co2_out(df: pd.DataFrame) -> pd.DataFrame:
        required = ["Cathode inlet CO2 gas flow", "Flow CO out"]
        if not all(col in df.columns for col in required):
            return df
        df = df.copy()
        CO2_inflow = pd.to_numeric(df["Cathode inlet CO2 gas flow"], errors="coerce")
        CO_outflow = pd.to_numeric(df["Flow CO out"], errors="coerce")
        df["Flow CO2 out, total"] = CO2_inflow - CO_outflow
        df["Flow CO2 out, total"] = df["Flow CO2 out, total"].replace(
            [np.inf, -np.inf], np.nan
        )
        return df

    @staticmethod
    def add_flow_rate_co2_out_anode(df: pd.DataFrame) -> pd.DataFrame:
        required = ["CO2:O2 ratio in anode product gas", "Flow O2 out"]
        if not all(col in df.columns for col in required):
            return df
        df = df.copy()
        CO2_O2_ratio = (
            pd.to_numeric(df["CO2:O2 ratio in anode product gas"], errors="coerce")
            / 100
        )
        O2_flow = pd.to_numeric(df["Flow O2 out"], errors="coerce")
        df["Flow CO2 out, anode"] = (CO2_O2_ratio * O2_flow) / (1 - CO2_O2_ratio)
        df["Flow CO2 out, anode"] = df["Flow CO2 out, anode"].replace(
            [np.inf, -np.inf], np.nan
        )
        return df

    @staticmethod
    def add_flow_rate_co2_out_cathode(df: pd.DataFrame) -> pd.DataFrame:
        required = ["Flow CO2 out, anode", "Flow CO2 out, total"]
        if not all(col in df.columns for col in required):
            return df
        df = df.copy()
        CO2_out_total = pd.to_numeric(df["Flow CO2 out, total"], errors="coerce")
        CO2_out_anode = pd.to_numeric(df["Flow CO2 out, anode"], errors="coerce")
        df["Flow CO2 out, cathode"] = CO2_out_total - CO2_out_anode
        df["Flow CO2 out, cathode"] = df["Flow CO2 out, cathode"].replace(
            [np.inf, -np.inf], np.nan
        )
        return df

    @staticmethod
    def add_ratio_co_h2(df: pd.DataFrame) -> pd.DataFrame:
        required = ["Flow H2 out", "Flow CO out"]
        if not all(col in df.columns for col in required):
            return df
        df = df.copy()
        H2_flow = pd.to_numeric(df["Flow H2 out"], errors="coerce")
        CO_flow = pd.to_numeric(df["Flow CO out"], errors="coerce")
        df["CO/H2 ratio recalculated"] = CO_flow / H2_flow
        df["CO/H2 ratio recalculated"] = df["CO/H2 ratio recalculated"].replace(
            [np.inf, -np.inf], np.nan
        )
        return df

    @staticmethod
    def add_faradaic_efficiency_co_h2(df: pd.DataFrame) -> pd.DataFrame:
        required = ["Faradaic Efficiency of CO", "Faradaic Efficiency of H2"]
        if not all(col in df.columns for col in required):
            return df
        df = df.copy()
        fe_co = pd.to_numeric(df["Faradaic Efficiency of CO"], errors="coerce")
        fe_h2 = pd.to_numeric(df["Faradaic Efficiency of H2"], errors="coerce")
        df["Faradaic Efficiency of CO and H2"] = fe_co + fe_h2
        df["Faradaic Efficiency of CO and H2"] = df[
            "Faradaic Efficiency of CO and H2"
        ].replace([np.inf, -np.inf], np.nan)
        return df

    @staticmethod
    def add_single_pass_conversion_efficiency(df: pd.DataFrame) -> pd.DataFrame:
        required = [
            "Faradaic Efficiency of CO",
            "Current",
            "Cathode inlet CO2 gas flow",
        ]
        if not all(col in df.columns for col in required):
            return df
        df = df.copy()
        FECO = pd.to_numeric(df["Faradaic Efficiency of CO"], errors="coerce") / 100
        I = pd.to_numeric(df["Current"], errors="coerce")
        F = 96485.3  # Faraday's constant in C/mol
        CO_formation_rate = (I * FECO) / (2 * F)  # mol/s
        CO2_inflow = (
            pd.to_numeric(df["Cathode inlet CO2 gas flow"], errors="coerce") / 60 / 5
        )  # nlpm to nL/s per cell
        Vm = 22.414  # l/mol at STP
        CO2_inflow_rate = CO2_inflow / Vm  # mol/s
        SPCE = 100 * CO_formation_rate / CO2_inflow_rate
        df["Single Pass Conversion Efficiency"] = SPCE
        df["Single Pass Conversion Efficiency"] = df[
            "Single Pass Conversion Efficiency"
        ].replace([np.inf, -np.inf], np.nan)
        return df

    @staticmethod
    def apply_plausibility_limits(df, units=None):
        """Clip columns with '%' unit to [0, 100]. Uses schema units dict."""
        df = df.copy()
        if units is None:
            units = {}
        for col in df.columns:
            unit = units.get(col, "")
            if unit == "%":
                df[col] = df[col].clip(lower=0, upper=100)
                df[col] = df[col].replace([np.inf, -np.inf], np.nan)
        return df

    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """Coerce all columns (except the first two) to numeric dtype.

        Non-numeric values are replaced with NaN.  This is typically run
        immediately after mapping, before enrichment.

        Args:
            df: Input DataFrame.

        Returns:
            DataFrame with numeric columns coerced.
        """
        cols = df.columns
        for col in cols[2:]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    @staticmethod
    def aggregate_timeseries(df: pd.DataFrame, interval_minutes=15) -> pd.DataFrame:
        """Aggregate a DataFrame into fixed time bins.

        For each bin the *min*, *max*, and *mean* of every numeric column are
        computed.  Non-numeric columns and ``Date``, ``Time``, ``Timestamp``
        are excluded.  The ``Elapsed time`` column is taken as the *first*
        value per bin (i.e. the bin start).

        Args:
            df: Source DataFrame (must contain an ``Elapsed time`` column in seconds).
            interval_minutes: Width of each time bin in minutes (default 15).

        Returns:
            Aggregated DataFrame with columns ``Elapsed time``, plus
            ``{col}_min``, ``{col}_max``, ``{col}_mean`` for each numeric column.

        Raises:
            ValueError: If ``Elapsed time`` is not present.
        """
        if "Elapsed time" not in df.columns:
            raise ValueError(
                "DataFrame must contain 'Elapsed time' column for aggregation."
            )
        interval_seconds = interval_minutes * 60.0
        bins = (df["Elapsed time"] // interval_seconds).astype(int)
        exclude = {"Elapsed time", "Date", "Time", "Timestamp"}
        numeric_cols = [
            col
            for col in df.columns
            if pd.api.types.is_numeric_dtype(df[col]) and col not in exclude
        ]
        grouped = df.groupby(bins)
        min_df = grouped[numeric_cols].min().add_suffix("_min")
        max_df = grouped[numeric_cols].max().add_suffix("_max")
        mean_df = grouped[numeric_cols].mean().add_suffix("_mean")
        time_df = grouped["Elapsed time"].first().to_frame()
        result = pd.concat([time_df, min_df, max_df, mean_df], axis=1).reset_index(
            drop=True
        )
        return result

