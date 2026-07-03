import json
import os
from typing import Any

from redis import RedisError

from backend.services.cache import cache_key, cache_set, get_redis_client
from backend.services.databricks import execute_sql_query
from backend.services.sql import DATABRICKS_CATALOG, LOCAL_SQL, to_sql_literal

CO_REPORTING_TTL_SECONDS = int(os.getenv("CO_REPORTING_TTL_SECONDS", "43200"))
CO_GOLD_CATALOG = os.getenv("CO_GOLD_CATALOG", DATABRICKS_CATALOG)
CO_GOLD_SCHEMA = os.getenv("CO_GOLD_SCHEMA", "co2elyd_dev")
CO_GOLD_RAW_TABLE = os.getenv("CO_GOLD_RAW_TABLE", "gold_timeseries")
CO_GOLD_AGG_1M_TABLE = os.getenv("CO_GOLD_AGG_1M_TABLE", "gold_timeseries_agg_1min")
CO_GOLD_AGG_15M_TABLE = os.getenv("CO_GOLD_AGG_15M_TABLE", "gold_timeseries_agg_15min")
CO_GOLD_AGG_60M_TABLE = os.getenv("CO_GOLD_AGG_60M_TABLE", "gold_timeseries_agg_60min")
CO_GOLD_EXPERIMENT_INDEX_TABLE = os.getenv("CO_GOLD_EXPERIMENT_INDEX_TABLE", "gold_experiment_index")
CO_GOLD_CHANNEL_CATALOG_EXPERIMENT_TABLE = os.getenv(
    "CO_GOLD_CHANNEL_CATALOG_EXPERIMENT_TABLE",
    os.getenv("CO_GOLD_CHANNEL_CATALOG_TABLE", "gold_channel_catalog_experiment"),
)
CO_REPORTING_DEFAULT_PREFETCH_SECONDS = int(os.getenv("CO_REPORTING_DEFAULT_PREFETCH_SECONDS", "1800"))
CO_REPORTING_RAW_MAX_SPAN_SECONDS = int(os.getenv("CO_REPORTING_RAW_MAX_SPAN_SECONDS", str(2 * 3600)))
CO_REPORTING_AGG_1M_MAX_SPAN_SECONDS = int(os.getenv("CO_REPORTING_AGG_1M_MAX_SPAN_SECONDS", str(24 * 3600)))
CO_REPORTING_AGG_15M_MAX_SPAN_SECONDS = int(os.getenv("CO_REPORTING_AGG_15M_MAX_SPAN_SECONDS", str(7 * 24 * 3600)))
CO_REPORTING_ENABLED_RESOLUTIONS = {
    item.strip()
    for item in os.getenv("CO_REPORTING_ENABLED_RESOLUTIONS", "raw,agg_1m,agg_15m,agg_60m").split(",")
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


def _table_for_resolution(resolution: str) -> str:
    if resolution == "raw":
        return _qualified_table(CO_GOLD_RAW_TABLE)
    if resolution == "agg_15m":
        return _qualified_table(CO_GOLD_AGG_15M_TABLE)
    if resolution == "agg_60m":
        return _qualified_table(CO_GOLD_AGG_60M_TABLE)
    return _qualified_table(CO_GOLD_AGG_1M_TABLE)


def _clamp_window(visible_start_s: float, visible_end_s: float, prefetch_margin_s: float) -> tuple[float, float]:
    start = min(visible_start_s, visible_end_s)
    end = max(visible_start_s, visible_end_s)
    margin = max(0.0, prefetch_margin_s)
    return max(0.0, start - margin), max(0.0, end + margin)


def _to_elapsed_literal(value: float) -> str:
    return str(round(float(value), 6))


def _experiment_literal(experiment_id: int | str) -> str:
    return str(int(experiment_id))


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _identity_condition(
    series: str,
    experiment_id: int | str | None = None,
    uuid: str | None = None,
    group: str | None = None,
) -> str:
    normalised_uuid = _optional_text(uuid)
    normalised_group = _optional_text(group)
    if experiment_id is None and (normalised_uuid is None or normalised_group is None):
        raise ValueError("CO reporting queries require experiment_id or both uuid and group")

    clauses = [f"series = {to_sql_literal(series)}"]
    if experiment_id is not None:
        clauses.append(f"experiment_id = {_experiment_literal(experiment_id)}")
    else:
        experiment_index_table = _qualified_table(CO_GOLD_EXPERIMENT_INDEX_TABLE)
        clauses.append(
            "experiment_id IN (\n"
            "            SELECT experiment_id\n"
            f"            FROM {experiment_index_table}\n"
            f"            WHERE series = {to_sql_literal(series)}\n"
            f"              AND uuid = {to_sql_literal(normalised_uuid)}\n"
            f"              AND `group` = {to_sql_literal(normalised_group)}\n"
            "          )"
        )
    return "\n          AND ".join(clauses)


def _channel_match_condition(channels: list[str]) -> str:
    channel_filter = ", ".join(to_sql_literal(channel) for channel in channels)
    return f"std_channel IN ({channel_filter})"


def _cache_get_or_query(key_prefix: str, query: str, source_name: str, **key_parts: Any) -> list[dict[str, Any]]:
    effective_ttl = 0 if LOCAL_SQL else CO_REPORTING_TTL_SECONDS
    key = cache_key(key_prefix, source=source_name, **key_parts)
    redis_client = None
    if effective_ttl > 0:
        try:
            redis_client = get_redis_client()
            cached = redis_client.get(key)
            if cached:
                return json.loads(cached)
        except RedisError:
            redis_client = None

    data = execute_sql_query(query)
    if effective_ttl > 0 and redis_client is not None:
        try:
            cache_set(redis_client, key, source_name, data, effective_ttl)
        except RedisError:
            pass
    return data


def _is_table_not_found_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "table_or_view_not_found" in message or "cannot be found" in message


def _list_series_groups_from_agg() -> list[dict[str, Any]]:
    table = _qualified_table(CO_GOLD_AGG_1M_TABLE)
    query = f"""
        SELECT
          experiment_id,
          series,
          CAST(NULL AS STRING) AS uuid,
          CAST(NULL AS STRING) AS `group`,
          MIN(elapsed_time_s) AS start_time_s,
          MAX(elapsed_time_s) AS end_time_s,
          MAX(elapsed_time_s) - MIN(elapsed_time_s) AS duration_s,
          MIN(timestamp) AS start_timestamp,
          MAX(timestamp) AS end_timestamp,
          COUNT(DISTINCT std_channel) AS channel_count,
          SUM(value_count) AS total_data_points,
          CAST(NULL AS STRING) AS source_file_name,
          CAST(NULL AS BIGINT) AS source_file_size,
          CAST(NULL AS TIMESTAMP) AS source_last_modified,
          CAST(NULL AS TIMESTAMP) AS ingested_at,
          CAST(NULL AS DOUBLE) AS avg_stack_voltage_v,
          CAST(NULL AS DOUBLE) AS peak_current_density_ma_cm2,
          CAST(NULL AS DOUBLE) AS avg_energy_efficiency_pct,
          CAST(NULL AS DOUBLE) AS avg_fe_co_pct,
          CAST(NULL AS DOUBLE) AS avg_fe_h2_pct,
          CAST(NULL AS DOUBLE) AS avg_spce_pct
        FROM {table}
        WHERE series IS NOT NULL
          AND experiment_id IS NOT NULL
        GROUP BY experiment_id, series
        ORDER BY series, start_timestamp, experiment_id
    """
    return _cache_get_or_query("co_reporting_series_fallback", query, table)


def list_series_groups() -> list[dict[str, Any]]:
    table = _qualified_table(CO_GOLD_EXPERIMENT_INDEX_TABLE)
    query = f"""
        SELECT
          experiment_id,
          series,
          uuid,
          `group`,
          start_time_s,
          end_time_s,
          duration_s,
          start_timestamp,
          end_timestamp,
          channel_count,
          total_data_points,
          source_file_name,
          source_file_size,
          source_last_modified,
          ingested_at,
          avg_stack_voltage_v,
          peak_current_density_ma_cm2,
          avg_energy_efficiency_pct,
          avg_fe_co_pct,
          avg_fe_h2_pct,
          avg_spce_pct
        FROM {table}
        WHERE series IS NOT NULL
          AND experiment_id IS NOT NULL
        ORDER BY series, start_timestamp, experiment_id
    """
    try:
        return _cache_get_or_query("co_reporting_series", query, table)
    except Exception as exc:
        if not _is_table_not_found_error(exc):
            raise
        return _list_series_groups_from_agg()


def list_channels(
    series: str,
    experiment_id: int | str | None = None,
    uuid: str | None = None,
    group: str | None = None,
) -> list[dict[str, Any]]:
    table = _qualified_table(CO_GOLD_CHANNEL_CATALOG_EXPERIMENT_TABLE)
    identity_condition = _identity_condition(
        series=series,
        experiment_id=experiment_id,
        uuid=uuid,
        group=group,
    )
    query = f"""
        SELECT
          signal_id,
          std_channel,
          std_channel AS channel_name,
          unit,
          has_data
        FROM {table}
        WHERE {identity_condition}
          AND std_channel IS NOT NULL
          AND COALESCE(has_data, true) = true
        ORDER BY std_channel
    """
    return _cache_get_or_query(
        "co_reporting_channels",
        query,
        table,
        series=series,
        experiment_id=experiment_id,
        uuid=uuid,
        group=group,
    )


def get_timeseries(
    series: str,
    experiment_id: int | str | None,
    channels: list[str],
    resolution: str,
    uuid: str | None = None,
    group: str | None = None,
) -> list[dict[str, Any]]:
    if not channels:
        return []

    normalised_channels = _normalise_channels(channels)
    channel_condition = _channel_match_condition(normalised_channels)
    effective_resolution = _normalise_resolution(resolution)
    table = _table_for_resolution(effective_resolution)
    identity_condition = _identity_condition(
        series=series,
        experiment_id=experiment_id,
        uuid=uuid,
        group=group,
    )

    if effective_resolution == "raw":
        query = f"""
            SELECT
              timestamp,
              elapsed_time_s,
              sample_offset,
              std_channel,
              std_channel AS channel_name,
              signal_id,
              signal_id AS channel,
              value,
              value_str
            FROM {table}
            WHERE {identity_condition}
              AND {channel_condition}
            ORDER BY elapsed_time_s, sample_offset, signal_id
        """
    else:
        query = f"""
            SELECT
              timestamp,
              elapsed_time_s,
              elapsed_bin_s,
              std_channel,
              std_channel AS channel_name,
              signal_id,
              signal_id AS channel,
              value_mean,
              value_min,
              value_max,
              value_count
            FROM {table}
            WHERE {identity_condition}
              AND {channel_condition}
            ORDER BY elapsed_bin_s, signal_id
        """
        effective_resolution = "agg_1m" if effective_resolution == "agg" else effective_resolution

    return _cache_get_or_query(
        "co_reporting_timeseries",
        query,
        table,
        series=series,
        experiment_id=experiment_id,
        uuid=uuid,
        group=group,
        channels=normalised_channels,
        resolution=effective_resolution,
    )


def query_timeseries_window(
    series: str,
    experiment_id: int | str | None,
    channels: list[str],
    visible_start_s: float,
    visible_end_s: float,
    prefetch_margin_s: float | None = None,
    resolution: str = "auto",
    mode: str | None = None,
    report_id: str | None = None,
    include_band: bool | None = None,
    uuid: str | None = None,
    group: str | None = None,
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
    table = _table_for_resolution(served_resolution)
    identity_condition = _identity_condition(
        series=series,
        experiment_id=experiment_id,
        uuid=uuid,
        group=group,
    )

    if served_resolution == "raw":
        query = f"""
            SELECT
              timestamp,
              elapsed_time_s,
              sample_offset,
              std_channel,
              std_channel AS channel_name,
              signal_id,
              signal_id AS channel,
              value,
              value_str
            FROM {table}
            WHERE {identity_condition}
              AND elapsed_time_s IS NOT NULL
              AND elapsed_time_s >= {_to_elapsed_literal(query_start_s)}
              AND elapsed_time_s <= {_to_elapsed_literal(query_end_s)}
              AND {channel_condition}
            ORDER BY elapsed_time_s, sample_offset, signal_id
        """
    else:
        query = f"""
            SELECT
              timestamp,
              elapsed_time_s,
              elapsed_bin_s,
              std_channel,
              std_channel AS channel_name,
              signal_id,
              signal_id AS channel,
              value_mean,
              value_min,
              value_max,
              value_count
            FROM {table}
            WHERE {identity_condition}
              AND elapsed_time_s IS NOT NULL
              AND elapsed_time_s >= {_to_elapsed_literal(query_start_s)}
              AND elapsed_time_s <= {_to_elapsed_literal(query_end_s)}
              AND {channel_condition}
            ORDER BY elapsed_bin_s, signal_id
        """
        served_resolution = "agg_1m" if served_resolution == "agg" else served_resolution

    data = _cache_get_or_query(
        "co_reporting_query",
        query,
        table,
        series=series,
        experiment_id=experiment_id,
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
            "experiment_id": int(experiment_id) if experiment_id is not None else None,
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
