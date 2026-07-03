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


@dataclass(frozen=True)
class ElyticsSeries:
    series: str
    experiment_id: int
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
        for row in rows:
            series_name = str(row.get("series") or "").strip()
            experiment_id = row.get("experiment_id")
            if not series_name or experiment_id in (None, ""):
                continue
            start_time = row.get("start_time") or row.get("start_timestamp")
            end_time = row.get("end_time") or row.get("end_timestamp")
            series = ElyticsSeries(
                series=series_name,
                experiment_id=int(experiment_id),
                uuid=None if row.get("uuid") in (None, "") else str(row.get("uuid")),
                group=None if row.get("group") in (None, "") else str(row.get("group")),
                start_time=None if start_time in (None, "") else str(start_time),
                end_time=None if end_time in (None, "") else str(end_time),
                sample_count=row.get("sample_count") or row.get("total_data_points"),
                source_file_name=None if row.get("source_file_name") in (None, "") else str(row.get("source_file_name")),
            )
            items[series.key] = series
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

    def load_timeseries(
        self,
        series: ElyticsSeries,
        columns: list[str],
        resolution: str = "agg",
    ) -> pd.DataFrame:
        df = get_co_reporting_timeseries(
            series.series,
            series.experiment_id,
            channels=columns,
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
            channels=columns,
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
    def _pivot_timeseries(df: pd.DataFrame, resolution: str) -> pd.DataFrame:
        if df.empty:
            return df

        df = df.copy()
        if "std_channel" in df.columns:
            df["metric"] = df["std_channel"]
        else:
            df["metric"] = df["channel_name"].fillna(df["channel"])
        index_columns = ["timestamp", "elapsed_time_s"]
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
        wide = wide.rename(columns={"timestamp": "time", "elapsed_time_s": "Elapsed time"})
        wide["time"] = pd.to_datetime(wide["time"], errors="coerce", utc=True)
        wide = wide.sort_values("Elapsed time").reset_index(drop=True)
        return wide


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
        return ElyticsSeries(
            series=series_def["series"],
            experiment_id=int(series_def["experiment_id"]),
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
