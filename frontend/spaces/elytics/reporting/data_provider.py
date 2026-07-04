from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from services.backend_service import (
    get_co_reporting_channels,
    get_co_reporting_series,
    get_co_reporting_timeseries,
    query_co_reporting_timeseries,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
SCHEMA_PATH = CONFIG_DIR / "schema.csv"

DEFAULT_AGGREGATIONS = [1, 15, 60]
CHANNEL_ALIASES = {
    "ΔpGas inlet - Gas outlet": "Δp Gas inlet - Gas outlet",
}
DERIVED_CHANNEL_DEPENDENCIES = {
    "Δp Anolyte": ("Anolyte inlet pressure", "Anolyte outlet pressure"),
}


@dataclass(frozen=True)
class ElyticsSeries:
    series: str
    experiment_id: int | None
    uuid: str | None = None
    group: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    sample_count: int | None = None
    source_file_name: str | None = None

    @property
    def key(self) -> str:
        return " | ".join(
            str(part)
            for part in [self.series, self.group, self.source_file_name, self.start_time, self.experiment_id]
            if part not in (None, "")
        )


class ElyticsDataProvider:
    def __init__(self, space: str = "elytics") -> None:
        self.space = space

    def list_series(self) -> list[ElyticsSeries]:
        rows = get_co_reporting_series()
        items: dict[str, ElyticsSeries] = {}
        combined_groups: dict[tuple[str, str, str], list[ElyticsSeries]] = {}
        for row in rows:
            series_name = str(row.get("series") or "").strip()
            experiment_id = row.get("experiment_id")
            if not series_name or experiment_id in (None, ""):
                continue
            start_time = row.get("start_time") or row.get("start_timestamp")
            end_time = row.get("end_time") or row.get("end_timestamp")
            uuid_value = None if row.get("uuid") in (None, "") else str(row.get("uuid"))
            source_file_name = None if row.get("source_file_name") in (None, "") else str(row.get("source_file_name"))
            series = ElyticsSeries(
                series=series_name,
                experiment_id=int(experiment_id),
                uuid=uuid_value,
                group=None if row.get("group") in (None, "") else str(row.get("group")),
                start_time=None if start_time in (None, "") else str(start_time),
                end_time=None if end_time in (None, "") else str(end_time),
                sample_count=row.get("sample_count") or row.get("total_data_points"),
                source_file_name=source_file_name,
            )
            items[series.key] = series
            if uuid_value and source_file_name:
                combined_groups.setdefault((series_name, uuid_value, source_file_name), []).append(series)

        for (series_name, uuid_value, source_file_name), group_items in combined_groups.items():
            unique_groups = {item.group for item in group_items if item.group}
            if len(unique_groups) < 2:
                continue
            combined = ElyticsSeries(
                series=series_name,
                experiment_id=None,
                uuid=uuid_value,
                group=None,
                start_time=min((item.start_time for item in group_items if item.start_time), default=None),
                end_time=max((item.end_time for item in group_items if item.end_time), default=None),
                sample_count=sum(int(item.sample_count or 0) for item in {item.experiment_id: item for item in group_items}.values()),
                source_file_name=f"{source_file_name} (all measurements)",
            )
            items[combined.key] = combined
        return sorted(items.values(), key=lambda item: item.key)

    def get_series_map(self) -> dict[str, ElyticsSeries]:
        return {series.key: series for series in self.list_series()}

    def list_channels(self, series: ElyticsSeries) -> list[dict]:
        return get_co_reporting_channels(
            series.series,
            series.experiment_id,
            uuid=series.uuid,
            group=series.group,
        )

    @staticmethod
    def _channel_display_name(channel_row: dict) -> str | None:
        return channel_row.get("std_channel") or channel_row.get("channel_name")

    @staticmethod
    def _canonical_channel_name(column: str) -> str:
        return CHANNEL_ALIASES.get(column, column)

    @staticmethod
    def _expand_requested_columns(columns: list[str]) -> list[str]:
        expanded: list[str] = []
        for column in columns:
            canonical_column = ElyticsDataProvider._canonical_channel_name(column)
            dependencies = DERIVED_CHANNEL_DEPENDENCIES.get(canonical_column)
            source_columns = dependencies if dependencies is not None else (canonical_column,)
            for source_column in source_columns:
                if source_column not in expanded:
                    expanded.append(source_column)
        return expanded

    def load_timeseries(
        self,
        series: ElyticsSeries,
        columns: list[str],
        resolution: str = "agg",
    ) -> pd.DataFrame:
        df = get_co_reporting_timeseries(
            series.series,
            series.experiment_id,
            channels=self._expand_requested_columns(columns),
            resolution=resolution,
            uuid=series.uuid,
            group=series.group,
        )
        return self._pivot_timeseries(df, resolution=resolution)

    def query_timeseries_window(
        self,
        series: ElyticsSeries,
        columns: list[str],
        visible_start_s: float,
        visible_end_s: float,
        prefetch_margin_s: float | None = None,
        resolution: str = "auto",
        mode: str | None = None,
        report_id: str | None = None,
        include_band: bool | None = None,
    ) -> pd.DataFrame:
        df = query_co_reporting_timeseries(
            series.series,
            series.experiment_id,
            channels=self._expand_requested_columns(columns),
            visible_start_s=visible_start_s,
            visible_end_s=visible_end_s,
            prefetch_margin_s=prefetch_margin_s,
            resolution=resolution,
            mode=mode,
            report_id=report_id,
            include_band=include_band,
            uuid=series.uuid,
            group=series.group,
        )
        served_resolution = str(df.attrs.get("meta", {}).get("served_resolution") or resolution)
        pivot_resolution = "raw" if served_resolution == "raw" else "agg"
        wide = self._pivot_timeseries(df, resolution=pivot_resolution)
        wide.attrs["meta"] = df.attrs.get("meta", {})
        return wide

    @staticmethod
    def _strip_aggregation_suffix(column: str) -> str:
        for suffix in ("_mean", "_min", "_max"):
            if column.endswith(suffix):
                return column[: -len(suffix)]
        return column

    @staticmethod
    def _apply_plausibility_limits(df: pd.DataFrame) -> pd.DataFrame:
        units = _load_units()
        if not units:
            return df
        df = df.copy()
        for column in df.columns:
            base = ElyticsDataProvider._strip_aggregation_suffix(column)
            if units.get(base) == "%":
                values = pd.to_numeric(df[column], errors="coerce")
                df[column] = values.clip(lower=0, upper=100)
        return df

    @staticmethod
    def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        derived_pairs = {
            "": ("", ""),
            "_mean": ("_mean", "_mean"),
            "_min": ("_min", "_max"),
            "_max": ("_max", "_min"),
        }
        for derived, (left, right) in DERIVED_CHANNEL_DEPENDENCIES.items():
            for target_suffix, (left_suffix, right_suffix) in derived_pairs.items():
                target = f"{derived}{target_suffix}"
                left_column = f"{left}{left_suffix}"
                right_column = f"{right}{right_suffix}"
                if target not in df.columns and left_column in df.columns and right_column in df.columns:
                    left_values = pd.to_numeric(df[left_column], errors="coerce")
                    right_values = pd.to_numeric(df[right_column], errors="coerce")
                    df[target] = (left_values - right_values).replace([float("inf"), float("-inf")], pd.NA)
        for alias, canonical in CHANNEL_ALIASES.items():
            for suffix in ("", "_mean", "_min", "_max"):
                alias_column = f"{alias}{suffix}"
                canonical_column = f"{canonical}{suffix}"
                if alias_column not in df.columns and canonical_column in df.columns:
                    df[alias_column] = df[canonical_column]
        return ElyticsDataProvider._apply_plausibility_limits(df)

    @staticmethod
    def _pivot_timeseries(df: pd.DataFrame, resolution: str) -> pd.DataFrame:
        if df.empty:
            return df

        df = df.copy()
        metric = None
        for column in ("std_channel", "channel_name", "raw_channel", "channel_id", "channel", "signal_id"):
            if column in df.columns:
                values = df[column]
                metric = values if metric is None else metric.fillna(values)
        if metric is None:
            return pd.DataFrame()
        df["metric"] = metric.astype(str)

        elapsed_column = "elapsed_time_s"
        if resolution != "raw" and "elapsed_bin_s" in df.columns:
            elapsed_column = "elapsed_bin_s"
        index_columns = [elapsed_column]
        timestamps = None
        if "timestamp" in df.columns:
            timestamps = df.groupby(elapsed_column, dropna=False)["timestamp"].first()

        if resolution == "raw":
            wide = df.pivot_table(
                index=index_columns,
                columns="metric",
                values="value",
                aggfunc="first",
            ).reset_index()
        else:
            value_frames = []
            for source, suffix in (
                ("value_mean", "_mean"),
                ("value_min", "_min"),
                ("value_max", "_max"),
            ):
                if source not in df.columns:
                    continue
                part = df.pivot_table(
                    index=index_columns,
                    columns="metric",
                    values=source,
                    aggfunc="first",
                )
                part.columns = [f"{column}{suffix}" for column in part.columns]
                value_frames.append(part)
            wide = pd.concat(value_frames, axis=1).reset_index() if value_frames else pd.DataFrame()

        if wide.empty:
            return wide
        if timestamps is not None:
            wide.insert(0, "timestamp", wide[elapsed_column].map(timestamps))
        else:
            wide.insert(0, "timestamp", pd.NaT)
        wide = wide.rename(columns={"timestamp": "time", elapsed_column: "Elapsed time"})
        wide["time"] = pd.to_datetime(wide["time"], errors="coerce", utc=True)
        wide = wide.sort_values("Elapsed time").reset_index(drop=True)
        return ElyticsDataProvider._add_derived_columns(wide)


def _load_units() -> dict[str, str]:
    units: dict[str, str] = {}
    try:
        with SCHEMA_PATH.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                name = (row.get("name") or "").strip()
                unit = (row.get("unit") or "").strip()
                if name and unit:
                    units.setdefault(name, unit)
    except OSError:
        logger.debug("Schema file not available at %s", SCHEMA_PATH)
    return units


class ElyticsDataManager(ElyticsDataProvider):
    """SeriesDataManager-compatible facade backed by Elytics API routes."""

    def __init__(self, space: str = "elytics") -> None:
        super().__init__(space=space)
        self.loaded_series: dict[str, pd.DataFrame] = {}
        self.units = _load_units()
        self._series_defs: dict[str, dict] | None = None

    @property
    def series_defs(self) -> dict[str, dict]:
        if not self._series_defs:
            self.refresh_series_defs()
        return self._series_defs or {}

    def refresh_series_defs(self) -> dict[str, dict]:
        try:
            series_items = self.list_series()
        except Exception:
            logger.warning("CO reporting backend is unavailable; showing Elytics UI without series data.")
            if self._series_defs is None:
                self._series_defs = {}
            return self._series_defs

        self._series_defs = {
            item.key: {
                "name": item.key,
                "series": item.series,
                "experiment_id": item.experiment_id,
                "uuid": item.uuid,
                "group": item.group,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "sample_count": item.sample_count,
                "source_file_name": item.source_file_name,
                "aggregations": DEFAULT_AGGREGATIONS,
            }
            for item in series_items
        }
        return self._series_defs

    def _series_from_key(self, series_name: str) -> ElyticsSeries | None:
        series_def = self.series_defs.get(series_name)
        if not series_def:
            self.refresh_series_defs()
            series_def = self.series_defs.get(series_name)
        if not series_def:
            return None
        experiment_id = series_def.get("experiment_id")
        return ElyticsSeries(
            series=series_def["series"],
            experiment_id=None if experiment_id in (None, "") else int(experiment_id),
            uuid=series_def.get("uuid"),
            group=series_def.get("group"),
            start_time=series_def.get("start_time"),
            end_time=series_def.get("end_time"),
            sample_count=series_def.get("sample_count"),
            source_file_name=series_def.get("source_file_name"),
        )

    @staticmethod
    def _parse_agg_name(name: str) -> tuple[str, int | None]:
        match = re.match(r"^(.+)_agg(\d+)min$", name)
        if match:
            return match.group(1), int(match.group(2))
        return name, None

    def load_series_frame(self, series_name: str, force_reload: bool = False) -> pd.DataFrame:
        if not force_reload and series_name in self.loaded_series:
            return self.loaded_series[series_name]

        parent, interval = self._parse_agg_name(series_name)
        series = self._series_from_key(parent)
        if series is None:
            logger.warning("Series %s is not available from CO reporting metadata", parent)
            return pd.DataFrame()

        # Fetch every available channel for this series (not just the
        # columns referenced by standard_reports.json) so the Custom
        # Reports tab can plot any signal via classify_columns(). Kept as a
        # local value (not stashed on self) since data_manager is a shared
        # singleton across concurrent Dash requests.
        #
        # Parent series (no "_aggNmin" suffix) map to the raw gold_timeseries
        # table; aggregate suffixes map to the materialized aggregate tiers.
        # The finished pipeline identifies the selected experiment by
        # experiment_id and filters channels by std_channel for file skipping.
        channel_catalog = self._load_channel_catalog(series)
        channels = [
            row.get("std_channel")
            for row in channel_catalog
            if row.get("std_channel")
        ]
        resolution = "raw" if interval is None else "agg"
        df = self.load_timeseries(series, channels, resolution=resolution)

        df = self._normalise_frame(df)
        self.loaded_series[series_name] = df
        return df

    def _load_channel_catalog(self, series: ElyticsSeries) -> list[dict]:
        try:
            channels = self.list_channels(series)
        except Exception:
            logger.exception("Could not load channel metadata for %s", series.key)
            return []
        for row in channels:
            name = self._channel_display_name(row)
            unit = row.get("unit")
            if name and unit:
                self.units[name] = unit
        return channels

    def unload_series(self, series_name: str) -> None:
        self.loaded_series.pop(series_name, None)

    def _normalise_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
            df = df.sort_values("time").reset_index(drop=True)
            if "Elapsed time" not in df.columns and df["time"].notna().any():
                start_time = df.loc[df["time"].notna(), "time"].iloc[0]
                df["Elapsed time"] = (df["time"] - start_time).dt.total_seconds()

        excluded_columns = {"series", "uuid", "group", "time", "bucket_start", "experiment_id", "signal_id"}
        for column in df.columns:
            if column not in excluded_columns:
                df[column] = pd.to_numeric(df[column], errors="ignore")
        return df
