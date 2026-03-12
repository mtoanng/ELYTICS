import hashlib
import json
import os
import re
from typing import Any

from databricks import sql as databricks_sql
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# 60 minutes cache TTL for table payloads.
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

# Redis maxmemory: 2GB by default.
REDIS_MAX_MEMORY_BYTES = int(os.getenv("REDIS_MAX_MEMORY_BYTES", str(2 * 1024 * 1024 * 1024)))

# All keys and least recently used eviction policy by default.
REDIS_MAX_MEMORY_POLICY = os.getenv("REDIS_MAX_MEMORY_POLICY", "allkeys-lru")

DEFAULT_DATABRICKS_CATALOG = os.getenv("DATABRICKS_CATALOG", "ps_xplatform_prod")
DEFAULT_DATABRICKS_SCHEMA = os.getenv("DATABRICKS_SCHEMA", "pemely_ops")

MAX_LIMIT = int(os.getenv("TABLE_MAX_LIMIT", "5000"))

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def get_redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


def configure_redis_cache_policy() -> None:
    """Configure runtime Redis limits for cache behavior."""
    client = get_redis_client()
    try:
        client.config_set("maxmemory", REDIS_MAX_MEMORY_BYTES)
        client.config_set("maxmemory-policy", REDIS_MAX_MEMORY_POLICY)
    except redis.RedisError:
        # Cache policy tuning is best effort (managed Redis may block CONFIG SET).
        return


def _validate_identifier(identifier: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier}")
    return identifier


def _to_sql_literal(value: str) -> str:
    lowered = value.lower()
    if lowered == "null":
        return "NULL"
    if lowered in {"true", "false"}:
        return lowered.upper()

    # Numeric passthrough.
    if re.fullmatch(r"-?\d+", value):
        return value
    if re.fullmatch(r"-?\d+\.\d+", value):
        return value

    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _build_where_clause(filters: dict[str, list[str]]) -> str:
    if not filters:
        return ""

    clauses: list[str] = []
    for column, values in filters.items():
        safe_column = _validate_identifier(column)
        safe_values = [_to_sql_literal(v) for v in values if v is not None]
        if not safe_values:
            continue
        if len(safe_values) == 1:
            clauses.append(f"{safe_column} = {safe_values[0]}")
        else:
            clauses.append(f"{safe_column} IN ({', '.join(safe_values)})")

    if not clauses:
        return ""
    return " WHERE " + " AND ".join(clauses)


def build_view_query(
    fully_qualified_view_name: str,
    filters: dict[str, list[str]] | None = None,
    sort_by: str | None = None,
    sort_dir: str = "asc",
    limit: int = 100,
    offset: int = 0,
) -> str:
    filters = filters or {}
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    if offset < 0:
        raise ValueError("offset must be >= 0")

    query = f"SELECT * FROM {fully_qualified_view_name}"
    query += _build_where_clause(filters)

    if sort_by:
        safe_sort = _validate_identifier(sort_by)
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
        query += f" ORDER BY {safe_sort} {direction}"

    query += f" LIMIT {limit} OFFSET {offset}"
    return query


def _build_cache_key(
    view_name: str,
    filters: dict[str, list[str]],
    sort_by: str | None,
    sort_dir: str,
    limit: int,
    offset: int,
) -> str:
    payload = {
        "view": view_name,
        "filters": {k: sorted(v) for k, v in sorted(filters.items())},
        "sort_by": sort_by,
        "sort_dir": sort_dir.lower(),
        "limit": limit,
        "offset": offset,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"holmes:table:{digest}"


def _execute_query(query: str) -> list[dict[str, Any]]:
    server_hostname = os.environ.get("DATABRICKS_SERVER_HOSTNAME")
    http_path = os.environ.get("DATABRICKS_HTTP_PATH")
    access_token = os.environ.get("DATABRICKS_TOKEN")

    if not (server_hostname and http_path and access_token):
        raise ValueError("Missing Databricks connection info in environment variables.")

    with databricks_sql.connect(
        server_hostname=server_hostname,
        http_path=http_path,
        access_token=access_token,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

    return [dict(zip(columns, row)) for row in rows]


def execute_sql_query(query: str) -> list[dict[str, Any]]:
    """Execute a Databricks SQL query and return row dictionaries."""
    return _execute_query(query)


def get_query_result(
    view_name: str,
    filters: dict[str, list[str]] | None = None,
    sort_by: str | None = None,
    sort_dir: str = "asc",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    filters = filters or {}
    cache_key = _build_cache_key(
        view_name=view_name,
        filters=filters,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )

    redis_client = get_redis_client()
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    query = build_view_query(
        fully_qualified_view_name=view_name,
        filters=filters,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    data = _execute_query(query)
    redis_client.set(cache_key, json.dumps(data), ex=CACHE_TTL_SECONDS)
    return data


# Map external data_kind labels to the actual segment used in Databricks view names.
_DATA_KIND_VIEW_SEGMENT: dict[str, str] = {
    "data": "data",
    "metadata": "meta",
}


def fully_qualified_view(space: str, data_kind: str, table_name: str) -> str:
    safe_space = _validate_identifier(space)
    safe_table = _validate_identifier(table_name)
    # Translate external kind label to the segment used in the actual view name.
    view_segment = _DATA_KIND_VIEW_SEGMENT.get(data_kind, data_kind)
    safe_kind = _validate_identifier(view_segment)
    return (
        f"{DEFAULT_DATABRICKS_CATALOG}.{DEFAULT_DATABRICKS_SCHEMA}."
        f"holmes_{safe_space}_{safe_kind}_{safe_table}_view"
    )


def human_readable_bytes(num_bytes: float) -> str:
    """Format byte values as human-readable units."""
    value = float(max(num_bytes, 0))
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    if idx == 0:
        return f"{int(value)} {units[idx]}"
    return f"{value:.2f} {units[idx]}"