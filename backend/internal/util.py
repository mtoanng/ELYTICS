import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from databricks import sql as databricks_sql
import redis

from backend.internal.metrics import record_query

logger = logging.getLogger(__name__)

DATABRICKS_SERVER_HOSTNAME = os.environ["DATABRICKS_SERVER_HOSTNAME"]
DATABRICKS_HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]
DATABRICKS_TOKEN = os.environ["DATABRICKS_TOKEN"]
DATABRICKS_CATALOG = os.getenv("DATABRICKS_CATALOG", "ps_xplatform_dev")
DATABRICKS_SCHEMA = os.getenv("DATABRICKS_SCHEMA", "pemely_dev")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

_TARGET_POINTS_DEFAULT = 1200
_TARGET_POINTS_MIN = 100
_TARGET_POINTS_MAX = 5000
_BUCKET_SECONDS_MIN = 1
_BUCKET_SECONDS_MAX = 30 * 24 * 60 * 60
_BUCKET_SECONDS_CHOICES = (
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

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CONNECTION_LOCK = threading.Lock()
_THREAD_CONNECTIONS: dict[int, Any] = {}


_redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True,
    max_connections=20,
)


def get_redis_client() -> redis.Redis:
    return redis.Redis(connection_pool=_redis_pool)


def configure_redis_cache_policy(
    max_memory_bytes: int = 2 * 1024 * 1024 * 1024,
) -> None:
    client = get_redis_client()
    try:
        client.config_set("maxmemory", max_memory_bytes)
        client.config_set("maxmemory-policy", "allkeys-lru")
    except redis.RedisError:
        pass


def _validate_identifier(identifier: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier!r}")
    return identifier


def _to_sql_literal(value: str) -> str:
    lowered = value.lower()
    if lowered == "null":
        return "NULL"
    if lowered in {"true", "false"}:
        return lowered.upper()
    if re.fullmatch(r"-?\d+", value):
        return value
    if re.fullmatch(r"-?\d+\.\d+", value):
        return value
    return f"'{value.replace(chr(39), chr(39)*2)}'"


def _build_filter_conditions(filters: dict[str, list[str]]) -> list[str]:
    clauses: list[str] = []
    for column, values in filters.items():
        safe_col = _validate_identifier(column)
        safe_vals = [_to_sql_literal(v) for v in values if v is not None]
        if not safe_vals:
            continue
        if len(safe_vals) == 1:
            clauses.append(f"{safe_col} = {safe_vals[0]}")
        else:
            clauses.append(f"{safe_col} IN ({', '.join(safe_vals)})")
    return clauses


def _to_sql_timestamp_literal(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return f"CAST('{value.strftime('%Y-%m-%d %H:%M:%S')}' AS TIMESTAMP)"


def _cache_key(prefix: str, **kwargs: Any) -> str:
    digest = hashlib.sha256(
        json.dumps(kwargs, sort_keys=True, default=str).encode()
    ).hexdigest()
    return f"holmes:{prefix}:{digest}"


def _cache_set(
    r: redis.Redis, key: str, view_name: str, payload: Any, ttl: int
) -> None:
    r.set(key, json.dumps(payload, default=str), ex=ttl)
    r.sadd(f"holmes:index:{view_name}", key)


def invalidate_view_cache(view_name: str) -> None:
    r = get_redis_client()
    index_key = f"holmes:index:{view_name}"
    keys = r.smembers(index_key)
    if keys:
        r.delete(*keys)
    r.delete(index_key)


def fully_qualified_view(space: str, data_kind: str, table_name: str) -> str:
    safe_space = _validate_identifier(space)
    safe_table = _validate_identifier(table_name)
    segment = "meta" if data_kind == "metadata" else data_kind
    safe_kind = _validate_identifier(segment)
    return f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.holmes_{safe_space}_{safe_table}_{safe_kind}_view"


def _connect_databricks() -> Any:
    return databricks_sql.connect(
        server_hostname=DATABRICKS_SERVER_HOSTNAME,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN,
    )


def _close_connection(connection: Any) -> None:
    try:
        connection.close()
    except Exception:
        logger.debug("Failed to close Databricks connection cleanly", exc_info=True)


def _thread_connection_id() -> int:
    return threading.get_ident()


def _get_or_create_connection() -> Any:
    thread_id = _thread_connection_id()
    with _CONNECTION_LOCK:
        connection = _THREAD_CONNECTIONS.get(thread_id)
        if connection is None:
            connection = _connect_databricks()
            _THREAD_CONNECTIONS[thread_id] = connection
        return connection


def _reset_thread_connection() -> Any:
    thread_id = _thread_connection_id()
    with _CONNECTION_LOCK:
        existing = _THREAD_CONNECTIONS.pop(thread_id, None)
        if existing is not None:
            _close_connection(existing)
        connection = _connect_databricks()
        _THREAD_CONNECTIONS[thread_id] = connection
        return connection


def close_all_databricks_connections() -> None:
    with _CONNECTION_LOCK:
        connections = list(_THREAD_CONNECTIONS.values())
        _THREAD_CONNECTIONS.clear()
    for connection in connections:
        _close_connection(connection)


def _should_reconnect(exc: Exception) -> bool:
    message = str(exc).lower()
    reconnect_markers = (
        "closed",
        "broken pipe",
        "connection reset",
        "connection aborted",
        "socket",
        "session",
        "transport",
        "eof",
        "timed out",
    )
    return any(marker in message for marker in reconnect_markers)


def execute_sql_query(query: str) -> list[dict[str, Any]]:
    connection = _get_or_create_connection()
    for attempt in range(2):
        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as exc:
            if attempt == 0 and _should_reconnect(exc):
                logger.warning(
                    "Databricks connection became unusable, reconnecting once"
                )
                connection = _reset_thread_connection()
                continue
            raise
    raise RuntimeError("Databricks query execution failed after retry")


def build_view_query(
    view: str,
    filters: dict[str, list[str]],
    sort_by: str | None,
    sort_dir: str,
) -> str:
    query = f"SELECT * FROM {view}"
    conditions = _build_filter_conditions(filters)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    if sort_by:
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
        query += f" ORDER BY {_validate_identifier(sort_by)} {direction}"
    return query


def get_query_result(
    view_name: str,
    space: str,
    table: str,
    filters: dict[str, list[str]] | None = None,
    sort_by: str | None = None,
    sort_dir: str = "asc",
    ttl: int = 3600,
) -> list[dict[str, Any]]:
    filters = filters or {}
    key = _cache_key(
        "tabular",
        view=view_name,
        filters={k: sorted(v) for k, v in sorted(filters.items())},
        sort_by=sort_by,
        sort_dir=sort_dir.lower(),
    )
    r = get_redis_client()
    cached = r.get(key)
    if cached:
        data: list[dict[str, Any]] = json.loads(cached)
        record_query(
            "tabular",
            space,
            table,
            cache_hit=True,
            duration_s=0,
            payload_bytes=len(cached),
            rows=len(data),
        )
        return data

    query = build_view_query(
        view=view_name, filters=filters, sort_by=sort_by, sort_dir=sort_dir
    )
    t0 = time.monotonic()
    data = execute_sql_query(query)
    duration = time.monotonic() - t0
    payload = json.dumps(data, default=str)
    _cache_set(r, key, view_name, data, ttl)
    record_query(
        "tabular",
        space,
        table,
        cache_hit=False,
        duration_s=duration,
        payload_bytes=len(payload),
        rows=len(data),
    )
    return data


def compute_bucket_seconds(
    start_time: datetime, end_time: datetime, target_points: int
) -> int:
    if not (_TARGET_POINTS_MIN <= target_points <= _TARGET_POINTS_MAX):
        raise ValueError(
            f"target_points must be between {_TARGET_POINTS_MIN} and {_TARGET_POINTS_MAX}"
        )
    if start_time >= end_time:
        raise ValueError("start must be before end")
    range_seconds = max((end_time - start_time).total_seconds(), 1.0)
    raw = range_seconds / target_points
    candidates = [
        bucket
        for bucket in _BUCKET_SECONDS_CHOICES
        if _BUCKET_SECONDS_MIN <= bucket <= _BUCKET_SECONDS_MAX
    ]
    if not candidates:
        raise ValueError("No valid bucket choices configured")

    # Choose the nearest fixed bucket; on ties prefer the larger bucket to keep
    # response sizes bounded.
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
    safe_time = _validate_identifier(time_column)
    safe_values: list[str] = []
    for col in value_columns:
        safe = _validate_identifier(col)
        if safe != safe_time and safe not in safe_values:
            safe_values.append(safe)
    if not safe_values:
        raise ValueError("At least one non-time metric column is required")

    agg_parts = [
        f"{fn}({col}) AS {col}_{fn.lower()}"
        for col in safe_values
        for fn in ("MIN", "MAX", "AVG")
    ]
    conditions = _build_filter_conditions(filters)
    conditions += [
        f"{safe_time} >= {_to_sql_timestamp_literal(start_time)}",
        f"{safe_time} < {_to_sql_timestamp_literal(end_time)}",
    ]
    where = " WHERE " + " AND ".join(conditions)
    bucket_expr = f"to_timestamp(floor(unix_timestamp({safe_time}) / {bucket_seconds}) * {bucket_seconds})"
    select = ", ".join([f"{bucket_expr} AS bucket_start", *agg_parts])
    return f"SELECT {select} FROM {view}{where} GROUP BY bucket_start ORDER BY bucket_start ASC"


def _resolve_timeseries_bounds(
    view_name: str,
    time_column: str,
    filters: dict[str, list[str]],
    start_time: datetime | None,
    end_time: datetime | None,
) -> tuple[datetime, datetime]:
    safe_time = _validate_identifier(time_column)

    query_start = start_time
    query_end = end_time
    if query_start is not None and query_end is not None:
        return query_start, query_end

    conditions = _build_filter_conditions(filters)
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
        # Include at least one full second when datasource min=max.
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
    target_points: int = _TARGET_POINTS_DEFAULT,
    ttl: int = 3600,
) -> dict[str, Any]:
    filters = filters or {}
    effective_start, effective_end = _resolve_timeseries_bounds(
        view_name=view_name,
        time_column=time_column,
        filters=filters,
        start_time=start_time,
        end_time=end_time,
    )
    bucket_seconds = compute_bucket_seconds(
        effective_start, effective_end, target_points
    )
    key = _cache_key(
        "timeseries",
        view=view_name,
        time_column=time_column,
        value_columns=sorted(value_columns),
        filters={k: sorted(v) for k, v in sorted(filters.items())},
        start=effective_start.isoformat(),
        end=effective_end.isoformat(),
        bucket_seconds=bucket_seconds,
    )
    r = get_redis_client()
    cached = r.get(key)
    if cached:
        record_query(
            "timeseries",
            space,
            table,
            cache_hit=True,
            duration_s=0,
            payload_bytes=len(cached),
            rows=0,
        )
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
    t0 = time.monotonic()
    data = execute_sql_query(query)
    duration = time.monotonic() - t0
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
    _cache_set(r, key, view_name, payload, ttl)
    record_query(
        "timeseries",
        space,
        table,
        cache_hit=False,
        duration_s=duration,
        payload_bytes=len(serialized),
        rows=len(data),
    )
    return payload


def human_readable_bytes(num_bytes: float) -> str:
    value = float(max(num_bytes, 0))
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    return f"{int(value)} {units[idx]}" if idx == 0 else f"{value:.2f} {units[idx]}"
