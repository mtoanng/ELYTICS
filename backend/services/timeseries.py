import json
from datetime import datetime, timedelta
from typing import Any

from backend.services.cache import cache_key, cache_set, get_redis_client
from backend.services.databricks import execute_sql_query
from backend.services.sql import (
    LOCAL_SQL,
    build_filter_conditions,
    to_sql_timestamp_literal,
    validate_identifier,
)

TARGET_POINTS_DEFAULT = 1200
TARGET_POINTS_MIN = 100
TARGET_POINTS_MAX = 5000
BUCKET_SECONDS_MIN = 1
BUCKET_SECONDS_MAX = 30 * 24 * 60 * 60
BUCKET_SECONDS_CHOICES = (
    1,
    5,
    10,
    15,
    30,
    60,
    5 * 60,
    10 * 60,
    15 * 60,
    30 * 60,
    60 * 60,
    2 * 60 * 60,
    6 * 60 * 60,
    12 * 60 * 60,
    24 * 60 * 60,
    7 * 24 * 60 * 60,
    30 * 24 * 60 * 60,
)


def compute_bucket_seconds(
    start_time: datetime,
    end_time: datetime,
    target_points: int,
) -> int:
    if not (TARGET_POINTS_MIN <= target_points <= TARGET_POINTS_MAX):
        raise ValueError(
            f"target_points must be between {TARGET_POINTS_MIN} and {TARGET_POINTS_MAX}"
        )
    if start_time >= end_time:
        raise ValueError("start must be before end")
    range_seconds = max((end_time - start_time).total_seconds(), 1.0)
    raw = range_seconds / target_points
    candidates = [
        bucket
        for bucket in BUCKET_SECONDS_CHOICES
        if BUCKET_SECONDS_MIN <= bucket <= BUCKET_SECONDS_MAX
    ]
    if not candidates:
        raise ValueError("No valid bucket choices configured")
    return min(candidates, key=lambda bucket: (abs(bucket - raw), -bucket))


def format_bucket_label(bucket_seconds: int) -> str:
    if bucket_seconds <= 0:
        return f"{bucket_seconds}s"
    if bucket_seconds % (24 * 60 * 60) == 0:
        return f"{bucket_seconds // (24 * 60 * 60)}d"
    if bucket_seconds % (60 * 60) == 0:
        return f"{bucket_seconds // (60 * 60)}h"
    if bucket_seconds % 60 == 0:
        return f"{bucket_seconds // 60}m"
    return f"{bucket_seconds}s"


def build_timeseries_query(
    view: str,
    time_column: str,
    value_columns: list[str],
    start_time: datetime,
    end_time: datetime,
    filters: dict[str, list[str]],
    bucket_seconds: int,
) -> str:
    safe_time = validate_identifier(time_column)
    safe_values: list[str] = []
    for col in value_columns:
        safe = validate_identifier(col)
        if safe != safe_time and safe not in safe_values:
            safe_values.append(safe)
    if not safe_values:
        raise ValueError("At least one non-time metric column is required")

    agg_parts = [
        f"ROUND({fn}({col}), 3) AS {col}_{fn.lower()}"
        for col in safe_values
        for fn in ("MIN", "MAX", "AVG")
    ]
    conditions = build_filter_conditions(filters)
    conditions += [
        f"{safe_time} >= {to_sql_timestamp_literal(start_time)}",
        f"{safe_time} < {to_sql_timestamp_literal(end_time)}",
    ]
    where = " WHERE " + " AND ".join(conditions)
    bucket_expr = (
        f"to_timestamp(floor(unix_timestamp({safe_time}) / {bucket_seconds}) * {bucket_seconds})"
    )
    select = ", ".join([f"{bucket_expr} AS bucket_start", *agg_parts])
    return (
        f"SELECT {select} FROM {view}{where} "
        "GROUP BY bucket_start ORDER BY bucket_start ASC"
    )


def resolve_timeseries_bounds(
    view_name: str,
    time_column: str,
    filters: dict[str, list[str]],
    start_time: datetime | None,
    end_time: datetime | None,
) -> tuple[datetime, datetime]:
    safe_time = validate_identifier(time_column)

    query_start = start_time
    query_end = end_time
    if query_start is not None and query_end is not None:
        return query_start, query_end

    conditions = build_filter_conditions(filters)
    conditions.append(f"{safe_time} IS NOT NULL")
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    bounds_query = (
        f"SELECT MIN({safe_time}) AS min_time, MAX({safe_time}) AS max_time "
        f"FROM {view_name}{where}"
    )
    bounds_rows = execute_sql_query(bounds_query)
    min_time = bounds_rows[0].get("min_time") if bounds_rows else None
    max_time = bounds_rows[0].get("max_time") if bounds_rows else None
    if min_time is None or max_time is None:
        raise ValueError("No time bounds available for selected filters")

    query_start = query_start or min_time
    query_end = query_end or max_time

    if not isinstance(query_start, datetime):
        query_start = datetime.fromisoformat(str(query_start).replace("Z", "+00:00"))
    if not isinstance(query_end, datetime):
        query_end = datetime.fromisoformat(str(query_end).replace("Z", "+00:00"))

    if query_start >= query_end:
        query_end = query_end.replace(microsecond=0)
        query_start = query_start.replace(microsecond=0)
        if query_start >= query_end:
            query_end = query_start + timedelta(seconds=1)

    return query_start, query_end


def get_timeseries_result(
    view_name: str,
    space: str,
    table: str,
    time_column: str,
    value_columns: list[str],
    start_time: datetime | None,
    end_time: datetime | None,
    filters: dict[str, list[str]] | None = None,
    target_points: int = TARGET_POINTS_DEFAULT,
    ttl: int = 3600,
    cache_source_name: str | None = None,
) -> dict[str, Any]:
    filters = filters or {}
    effective_ttl = 0 if LOCAL_SQL else ttl
    source_name = cache_source_name or view_name
    effective_start, effective_end = resolve_timeseries_bounds(
        view_name=view_name,
        time_column=time_column,
        filters=filters,
        start_time=start_time,
        end_time=end_time,
    )
    bucket_seconds = compute_bucket_seconds(
        effective_start,
        effective_end,
        target_points,
    )
    key = cache_key(
        "timeseries",
        view=source_name,
        time_column=time_column,
        value_columns=sorted(value_columns),
        filters={k: sorted(v) for k, v in sorted(filters.items())},
        start=effective_start.isoformat(),
        end=effective_end.isoformat(),
        bucket_seconds=bucket_seconds,
    )

    redis_client = get_redis_client()
    if effective_ttl > 0:
        cached = redis_client.get(key)
        if cached:
            return json.loads(cached)

    query = build_timeseries_query(
        view=view_name,
        time_column=time_column,
        value_columns=value_columns,
        start_time=effective_start,
        end_time=effective_end,
        filters=filters,
        bucket_seconds=bucket_seconds,
    )
    data = execute_sql_query(query)
    payload = {
        "data": data,
        "meta": {
            "bucket_seconds": bucket_seconds,
            "bucket_label": format_bucket_label(bucket_seconds),
            "requested_points": target_points,
            "returned_points": len(data),
            "effective_start": effective_start,
            "effective_end": effective_end,
        },
    }
    serialized = json.dumps(payload, default=str)
    if effective_ttl > 0:
        cache_set(redis_client, key, source_name, payload, effective_ttl)
    return payload
