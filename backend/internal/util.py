import hashlib
import json
import math
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

from databricks import sql as databricks_sql
import redis

from backend.internal.metrics import record_query

DATABRICKS_SERVER_HOSTNAME = os.environ["DATABRICKS_SERVER_HOSTNAME"]
DATABRICKS_HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]
DATABRICKS_TOKEN = os.environ["DATABRICKS_TOKEN"]
DATABRICKS_CATALOG = os.getenv("DATABRICKS_CATALOG", "ps_xplatform_prod")
DATABRICKS_SCHEMA = os.getenv("DATABRICKS_SCHEMA", "pemely_ops")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

_TARGET_POINTS_DEFAULT = 1200
_TARGET_POINTS_MIN = 100
_TARGET_POINTS_MAX = 5000
_BUCKET_SECONDS_MIN = 1
_BUCKET_SECONDS_MAX = 30 * 24 * 60 * 60

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def get_redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


def configure_redis_cache_policy(max_memory_bytes: int = 2 * 1024 * 1024 * 1024) -> None:
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


def _cache_set(r: redis.Redis, key: str, view_name: str, payload: Any, ttl: int) -> None:
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
    return f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.holmes_{safe_space}_{safe_kind}_{safe_table}_view"


def execute_sql_query(query: str) -> list[dict[str, Any]]:
    with databricks_sql.connect(
        server_hostname=DATABRICKS_SERVER_HOSTNAME,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def build_view_query(
    view: str,
    filters: dict[str, list[str]],
    sort_by: str | None,
    sort_dir: str,
    limit: int,
    offset: int,
) -> str:
    query = f"SELECT * FROM {view}"
    conditions = _build_filter_conditions(filters)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    if sort_by:
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
        query += f" ORDER BY {_validate_identifier(sort_by)} {direction}"
    query += f" LIMIT {limit} OFFSET {offset}"
    return query


def get_query_result(
    view_name: str,
    space: str,
    table: str,
    filters: dict[str, list[str]] | None = None,
    sort_by: str | None = None,
    sort_dir: str = "asc",
    limit: int = 100,
    offset: int = 0,
    ttl: int = 3600,
) -> list[dict[str, Any]]:
    filters = filters or {}
    key = _cache_key(
        "tabular",
        view=view_name,
        filters={k: sorted(v) for k, v in sorted(filters.items())},
        sort_by=sort_by,
        sort_dir=sort_dir.lower(),
        limit=limit,
        offset=offset,
    )
    r = get_redis_client()
    cached = r.get(key)
    if cached:
        record_query("tabular", space, table, cache_hit=True, duration_s=0, payload_bytes=len(cached), rows=0)
        return json.loads(cached)

    query = build_view_query(view=view_name, filters=filters, sort_by=sort_by, sort_dir=sort_dir, limit=limit, offset=offset)
    t0 = time.monotonic()
    data = execute_sql_query(query)
    duration = time.monotonic() - t0
    payload = json.dumps(data, default=str)
    _cache_set(r, key, view_name, data, ttl)
    record_query("tabular", space, table, cache_hit=False, duration_s=duration, payload_bytes=len(payload), rows=len(data))
    return data


def compute_bucket_seconds(start_time: datetime, end_time: datetime, target_points: int) -> int:
    if not (_TARGET_POINTS_MIN <= target_points <= _TARGET_POINTS_MAX):
        raise ValueError(f"target_points must be between {_TARGET_POINTS_MIN} and {_TARGET_POINTS_MAX}")
    if start_time >= end_time:
        raise ValueError("start must be before end")
    range_seconds = max((end_time - start_time).total_seconds(), 1.0)
    raw = math.ceil(range_seconds / target_points)
    return max(_BUCKET_SECONDS_MIN, min(raw, _BUCKET_SECONDS_MAX))


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

    agg_parts = [f"{fn}({col}) AS {col}_{fn.lower()}" for col in safe_values for fn in ("MIN", "MAX", "AVG")]
    conditions = _build_filter_conditions(filters)
    conditions += [
        f"{safe_time} >= {_to_sql_timestamp_literal(start_time)}",
        f"{safe_time} < {_to_sql_timestamp_literal(end_time)}",
    ]
    where = " WHERE " + " AND ".join(conditions)
    bucket_expr = f"to_timestamp(floor(unix_timestamp({safe_time}) / {bucket_seconds}) * {bucket_seconds})"
    select = ", ".join([f"{bucket_expr} AS bucket_start", *agg_parts])
    return f"SELECT {select} FROM {view}{where} GROUP BY bucket_start ORDER BY bucket_start ASC"


def get_timeseries_result(
    view_name: str,
    space: str,
    table: str,
    time_column: str,
    value_columns: list[str],
    start_time: datetime,
    end_time: datetime,
    filters: dict[str, list[str]] | None = None,
    target_points: int = _TARGET_POINTS_DEFAULT,
    ttl: int = 3600,
) -> dict[str, Any]:
    filters = filters or {}
    bucket_seconds = compute_bucket_seconds(start_time, end_time, target_points)
    key = _cache_key(
        "timeseries",
        view=view_name,
        time_column=time_column,
        value_columns=sorted(value_columns),
        filters={k: sorted(v) for k, v in sorted(filters.items())},
        start=start_time.isoformat(),
        end=end_time.isoformat(),
        target_points=target_points,
        bucket_seconds=bucket_seconds,
    )
    r = get_redis_client()
    cached = r.get(key)
    if cached:
        record_query("timeseries", space, table, cache_hit=True, duration_s=0, payload_bytes=len(cached), rows=0)
        return json.loads(cached)

    query = build_timeseries_query(
        view=view_name,
        time_column=time_column,
        value_columns=value_columns,
        start_time=start_time,
        end_time=end_time,
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
            "requested_points": target_points,
            "returned_points": len(data),
        },
    }
    serialized = json.dumps(payload, default=str)
    _cache_set(r, key, view_name, payload, ttl)
    record_query("timeseries", space, table, cache_hit=False, duration_s=duration, payload_bytes=len(serialized), rows=len(data))
    return payload


def human_readable_bytes(num_bytes: float) -> str:
    value = float(max(num_bytes, 0))
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    return f"{int(value)} {units[idx]}" if idx == 0 else f"{value:.2f} {units[idx]}"
