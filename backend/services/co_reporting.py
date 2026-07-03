import json
import os
from typing import Any

from backend.services.cache import cache_key, cache_set, get_redis_client
from backend.services.databricks import execute_sql_query
from backend.services.sql import DATABRICKS_CATALOG, LOCAL_SQL, to_sql_literal

CO_REPORTING_TTL_SECONDS = int(os.getenv("CO_REPORTING_TTL_SECONDS", "43200"))
CO_GOLD_CATALOG = os.getenv("CO_GOLD_CATALOG", DATABRICKS_CATALOG)
CO_GOLD_SCHEMA = os.getenv("CO_GOLD_SCHEMA", "co2elyd_dev")
CO_GOLD_RAW_TABLE = os.getenv("CO_GOLD_RAW_TABLE", "gold_timeseries")
CO_GOLD_AGG_TABLE = os.getenv("CO_GOLD_AGG_TABLE", "gold_timeseries_agg")
CO_GOLD_AGG_15M_TABLE = os.getenv("CO_GOLD_AGG_15M_TABLE", "gold_timeseries_agg_15min")
CO_GOLD_AGG_60M_TABLE = os.getenv("CO_GOLD_AGG_60M_TABLE", "gold_timeseries_agg_60min")
CO_GOLD_EXPERIMENT_INDEX_TABLE = os.getenv("CO_GOLD_EXPERIMENT_INDEX_TABLE", "gold_experiment_index")
CO_GOLD_CHANNEL_CATALOG_TABLE = os.getenv("CO_GOLD_CHANNEL_CATALOG_TABLE", "gold_channel_catalog")
CO_GOLD_SUMMARY_TABLE = os.getenv("CO_GOLD_SUMMARY_TABLE", "gold_summary_statistics")
CO_REPORTING_DEFAULT_PREFETCH_SECONDS = int(os.getenv("CO_REPORTING_DEFAULT_PREFETCH_SECONDS", "1800"))
CO_REPORTING_RAW_MAX_SPAN_SECONDS = int(os.getenv("CO_REPORTING_RAW_MAX_SPAN_SECONDS", str(2 * 3600)))
CO_REPORTING_AGG_1M_MAX_SPAN_SECONDS = int(os.getenv("CO_REPORTING_AGG_1M_MAX_SPAN_SECONDS", str(24 * 3600)))
CO_REPORTING_AGG_15M_MAX_SPAN_SECONDS = int(os.getenv("CO_REPORTING_AGG_15M_MAX_SPAN_SECONDS", str(7 * 24 * 3600)))
CO_REPORTING_ENABLED_RESOLUTIONS = {
    item.strip()
    for item in os.getenv("CO_REPORTING_ENABLED_RESOLUTIONS", "raw,agg_1m").split(",")
    if item.strip()
}

_RESOLUTION_ALIASES = {
    "agg": "agg_1m",
    "agg1": "agg_1m",
    "agg15": "agg_15m",
    "agg60": "agg_60m",
}


def _qualified_table(table_name: str) -> str:
    return f"{CO_GOLD_CATALOG}.{CO_GOLD_SCHEMA}.{table_name}"


def _normalise_channels(channels: list[str]) -> list[str]:
    return sorted({str(channel).strip() for channel in channels if str(channel).strip()})


def _normalise_resolution(resolution: str) -> str:
    return _RESOLUTION_ALIASES.get(str(resolution).strip(), str(resolution).strip())


def _choose_resolution(requested_resolution: str, span_seconds: float) -> str:
    requested = _normalise_resolution(requested_resolution)
    if requested != "auto":
        if requested in CO_REPORTING_ENABLED_RESOLUTIONS:
            return requested
        if requested in {"agg_15m", "agg_60m"} and "agg_1m" in CO_REPORTING_ENABLED_RESOLUTIONS:
            return "agg_1m"
        return "raw"

    if span_seconds <= CO_REPORTING_RAW_MAX_SPAN_SECONDS and "raw" in CO_REPORTING_ENABLED_RESOLUTIONS:
        return "raw"
    if span_seconds <= CO_REPORTING_AGG_1M_MAX_SPAN_SECONDS and "agg_1m" in CO_REPORTING_ENABLED_RESOLUTIONS:
        return "agg_1m"
    if span_seconds <= CO_REPORTING_AGG_15M_MAX_SPAN_SECONDS and "agg_15m" in CO_REPORTING_ENABLED_RESOLUTIONS:
        return "agg_15m"
    if "agg_60m" in CO_REPORTING_ENABLED_RESOLUTIONS:
        return "agg_60m"
    if "agg_1m" in CO_REPORTING_ENABLED_RESOLUTIONS:
        return "agg_1m"
    return "raw"


def _clamp_window(visible_start_s: float, visible_end_s: float, prefetch_margin_s: float) -> tuple[float, float]:
    start = min(visible_start_s, visible_end_s)
    end = max(visible_start_s, visible_end_s)
    margin = max(0.0, prefetch_margin_s)
    return max(0.0, start - margin), max(0.0, end + margin)


def _to_elapsed_literal(value: float) -> str:
    return str(round(float(value), 6))


def _channel_match_condition(channels: list[str]) -> str:
    channel_filter = ", ".join(to_sql_literal(channel) for channel in channels)
    return (
        f"(channel_id IN ({channel_filter}) "
        f"OR std_channel IN ({channel_filter}) "
        f"OR raw_channel IN ({channel_filter}))"
    )


def _cache_get_or_query(key_prefix: str, query: str, source_name: str, **key_parts: Any) -> list[dict[str, Any]]:
    effective_ttl = 0 if LOCAL_SQL else CO_REPORTING_TTL_SECONDS
    key = cache_key(key_prefix, source=source_name, **key_parts)
    redis_client = get_redis_client()
    if effective_ttl > 0:
        cached = redis_client.get(key)
        if cached:
            return json.loads(cached)

    data = execute_sql_query(query)
    if effective_ttl > 0:
        cache_set(redis_client, key, source_name, data, effective_ttl)
    return data


def list_series_groups() -> list[dict[str, Any]]:
    table = _qualified_table(CO_GOLD_EXPERIMENT_INDEX_TABLE)
    query = f"""
        SELECT
          series,
          uuid,
          `group`,
          start_time_s,
          end_time_s,
          duration_s,
          start_timestamp,
          end_timestamp,
          channel_count,
          max_sample_offset,
          total_data_points,
          source_file_path,
          source_file_name,
          source_file_size,
          source_last_modified,
          ingested_at
        FROM {table}
        WHERE series IS NOT NULL
          AND uuid IS NOT NULL
          AND `group` IS NOT NULL
        ORDER BY series, uuid, `group`
    """
    return _cache_get_or_query("co_reporting_series", query, table)


def list_channels(series: str, uuid: str, group: str) -> list[dict[str, Any]]:
    table = _qualified_table(CO_GOLD_CHANNEL_CATALOG_TABLE)
    query = f"""
        SELECT
          channel_id,
          raw_channel,
          std_channel,
          unit,
          column_index,
          has_data
        FROM {table}
        WHERE series = {to_sql_literal(series)}
          AND uuid = {to_sql_literal(uuid)}
          AND `group` = {to_sql_literal(group)}
          AND channel_id IS NOT NULL
          AND COALESCE(has_data, true) = true
        ORDER BY COALESCE(column_index, 2147483647), COALESCE(std_channel, raw_channel, channel_id), channel_id
    """
    return _cache_get_or_query(
        "co_reporting_channels",
        query,
        table,
        series=series,
        uuid=uuid,
        group=group,
    )


def get_timeseries(
    series: str,
    uuid: str,
    group: str,
    channels: list[str],
    resolution: str,
) -> list[dict[str, Any]]:
    if not channels:
        return []

    normalised_channels = _normalise_channels(channels)
    channel_condition = _channel_match_condition(normalised_channels)
    effective_resolution = _normalise_resolution(resolution)
    if effective_resolution == "raw":
        table = _qualified_table(CO_GOLD_RAW_TABLE)
        query = f"""
            SELECT
              timestamp,
              elapsed_time_s,
              sample_offset,
              channel_id,
              raw_channel,
              std_channel,
              unit,
              value,
              value_str
            FROM {table}
            WHERE series = {to_sql_literal(series)}
              AND uuid = {to_sql_literal(uuid)}
              AND `group` = {to_sql_literal(group)}
              AND {channel_condition}
            ORDER BY elapsed_time_s, sample_offset, channel_id
        """
    else:
        table = _qualified_table(CO_GOLD_AGG_TABLE)
        query = f"""
            SELECT
              timestamp,
              elapsed_time_s,
              elapsed_bin_s,
              channel_id,
              raw_channel,
              std_channel,
              unit,
              value_mean,
              value_min,
              value_max,
              value_count
            FROM {table}
            WHERE series = {to_sql_literal(series)}
              AND uuid = {to_sql_literal(uuid)}
              AND `group` = {to_sql_literal(group)}
              AND {channel_condition}
            ORDER BY elapsed_bin_s, channel_id
        """

    return _cache_get_or_query(
        "co_reporting_timeseries",
        query,
        table,
        series=series,
        uuid=uuid,
        group=group,
        channels=normalised_channels,
        resolution=effective_resolution,
    )


def query_timeseries_window(
    series: str,
    uuid: str,
    group: str,
    channels: list[str],
    visible_start_s: float,
    visible_end_s: float,
    prefetch_margin_s: float | None = None,
    resolution: str = "auto",
    mode: str | None = None,
    report_id: str | None = None,
    include_band: bool | None = None,
) -> dict[str, Any]:
    normalised_channels = _normalise_channels(channels)
    if not normalised_channels:
        return {"data": [], "meta": {"returned_points": 0, "channels_returned": 0}}

    effective_prefetch = (
        CO_REPORTING_DEFAULT_PREFETCH_SECONDS
        if prefetch_margin_s is None
        else float(prefetch_margin_s)
    )
    visible_min = min(float(visible_start_s), float(visible_end_s))
    visible_max = max(float(visible_start_s), float(visible_end_s))
    query_start_s, query_end_s = _clamp_window(
        visible_start_s=visible_min,
        visible_end_s=visible_max,
        prefetch_margin_s=effective_prefetch,
    )
    span_seconds = max(0.0, visible_max - visible_min)
    served_resolution = _choose_resolution(resolution, span_seconds)
    channel_condition = _channel_match_condition(normalised_channels)

    if served_resolution == "raw":
        table = _qualified_table(CO_GOLD_RAW_TABLE)
        query = f"""
            SELECT
              timestamp,
              elapsed_time_s,
              sample_offset,
              channel_id,
              raw_channel,
              std_channel,
              unit,
              value,
              value_str
            FROM {table}
            WHERE series = {to_sql_literal(series)}
              AND uuid = {to_sql_literal(uuid)}
              AND `group` = {to_sql_literal(group)}
              AND elapsed_time_s IS NOT NULL
              AND elapsed_time_s >= {_to_elapsed_literal(query_start_s)}
              AND elapsed_time_s <= {_to_elapsed_literal(query_end_s)}
              AND {channel_condition}
            ORDER BY elapsed_time_s, sample_offset, channel_id
        """
    elif served_resolution == "agg_60m":
        table = _qualified_table(CO_GOLD_AGG_60M_TABLE)
        query = f"""
            SELECT
              timestamp,
              elapsed_time_s,
              elapsed_bin_s,
              channel_id,
              raw_channel,
              std_channel,
              unit,
              value_mean,
              value_min,
              value_max,
              value_count
            FROM {table}
            WHERE series = {to_sql_literal(series)}
              AND uuid = {to_sql_literal(uuid)}
              AND `group` = {to_sql_literal(group)}
              AND elapsed_time_s IS NOT NULL
              AND elapsed_time_s >= {_to_elapsed_literal(query_start_s)}
              AND elapsed_time_s <= {_to_elapsed_literal(query_end_s)}
              AND {channel_condition}
            ORDER BY elapsed_bin_s, channel_id
        """
    elif served_resolution == "agg_15m":
        table = _qualified_table(CO_GOLD_AGG_15M_TABLE)
        query = f"""
            SELECT
              timestamp,
              elapsed_time_s,
              elapsed_bin_s,
              channel_id,
              raw_channel,
              std_channel,
              unit,
              value_mean,
              value_min,
              value_max,
              value_count
            FROM {table}
            WHERE series = {to_sql_literal(series)}
              AND uuid = {to_sql_literal(uuid)}
              AND `group` = {to_sql_literal(group)}
              AND elapsed_time_s IS NOT NULL
              AND elapsed_time_s >= {_to_elapsed_literal(query_start_s)}
              AND elapsed_time_s <= {_to_elapsed_literal(query_end_s)}
              AND {channel_condition}
            ORDER BY elapsed_bin_s, channel_id
        """
    else:
        table = _qualified_table(CO_GOLD_AGG_TABLE)
        query = f"""
            SELECT
              timestamp,
              elapsed_time_s,
              elapsed_bin_s,
              channel_id,
              raw_channel,
              std_channel,
              unit,
              value_mean,
              value_min,
              value_max,
              value_count
            FROM {table}
            WHERE series = {to_sql_literal(series)}
              AND uuid = {to_sql_literal(uuid)}
              AND `group` = {to_sql_literal(group)}
              AND elapsed_time_s IS NOT NULL
              AND elapsed_time_s >= {_to_elapsed_literal(query_start_s)}
              AND elapsed_time_s <= {_to_elapsed_literal(query_end_s)}
              AND {channel_condition}
            ORDER BY elapsed_bin_s, channel_id
        """
        served_resolution = "agg_1m"

    data = _cache_get_or_query(
        "co_reporting_query",
        query,
        table,
        series=series,
        uuid=uuid,
        group=group,
        channels=normalised_channels,
        resolution=served_resolution,
        query_start_s=round(query_start_s, 3),
        query_end_s=round(query_end_s, 3),
        mode=mode,
        report_id=report_id,
        include_band=include_band,
    )
    return {
        "data": data,
        "meta": {
            "series": series,
            "uuid": uuid,
            "group": group,
            "requested_resolution": resolution,
            "served_resolution": served_resolution,
            "visible_start_s": visible_min,
            "visible_end_s": visible_max,
            "query_start_s": query_start_s,
            "query_end_s": query_end_s,
            "returned_points": len(data),
            "channels_returned": len(normalised_channels),
            "source": table,
            "mode": mode,
            "report_id": report_id,
            "include_band": include_band,
        },
    }
