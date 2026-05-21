import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.cache import cache_key, cache_set, get_redis_client
from backend.services.databricks import execute_sql_query

DATABRICKS_CATALOG = os.getenv("DATABRICKS_CATALOG", "ps_xplatform_dev")
DATABRICKS_SCHEMA = os.getenv("DATABRICKS_SCHEMA", "pemely_dev")
LOCAL_SQL = os.getenv("LOCAL_SQL", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_identifier(identifier: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier!r}")
    return identifier


def to_sql_literal(value: str) -> str:
    lowered = value.lower()
    if lowered == "null":
        return "NULL"
    if lowered in {"true", "false"}:
        return lowered.upper()
    if re.fullmatch(r"-?\d+", value):
        return value
    if re.fullmatch(r"-?\d+\.\d+", value):
        return value
    return f"'{value.replace(chr(39), chr(39) * 2)}'"


def build_filter_conditions(filters: dict[str, list[str]]) -> list[str]:
    clauses: list[str] = []
    for column, values in filters.items():
        safe_col = validate_identifier(column)
        safe_vals = [to_sql_literal(v) for v in values if v is not None]
        if not safe_vals:
            continue
        if len(safe_vals) == 1:
            clauses.append(f"{safe_col} = {safe_vals[0]}")
        else:
            clauses.append(f"{safe_col} IN ({', '.join(safe_vals)})")
    return clauses


def to_sql_timestamp_literal(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return f"CAST('{value.strftime('%Y-%m-%d %H:%M:%S')}' AS TIMESTAMP)"


def fully_qualified_view(space: str, data_kind: str, table_name: str) -> str:
    safe_space = validate_identifier(space)
    safe_table = validate_identifier(table_name)
    segment = "meta" if data_kind == "metadata" else data_kind
    safe_kind = validate_identifier(segment)
    return f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.holmes_{safe_space}_{safe_table}_{safe_kind}_view"


def read_local_sql(path: str) -> str:
    sql = Path(path).read_text(encoding="utf-8").strip()
    return sql.rstrip(";")


def resolve_query_source(
    space: str,
    data_kind: str,
    table_name: str,
) -> tuple[str, str]:
    cache_source = fully_qualified_view(
        space=space,
        data_kind=data_kind,
        table_name=table_name,
    )
    if not LOCAL_SQL:
        return cache_source, cache_source

    safe_space = validate_identifier(space)
    safe_table = validate_identifier(table_name)
    segment = "meta" if data_kind == "metadata" else data_kind
    safe_kind = validate_identifier(segment)
    sql_file = (
        Path(__file__).resolve().parents[2]
        / "views"
        / "spaces"
        / safe_space
        / f"{safe_table}_{safe_kind}.sql"
    )
    sql_body = read_local_sql(str(sql_file))
    return f"({sql_body}) AS local_source", cache_source


def build_view_query(
    view: str,
    filters: dict[str, list[str]],
    sort_by: str | None,
    sort_dir: str,
) -> str:
    query = f"SELECT * FROM {view}"
    conditions = build_filter_conditions(filters)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    if sort_by:
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
        query += f" ORDER BY {validate_identifier(sort_by)} {direction}"
    return query


def get_query_result(
    view_name: str,
    space: str,
    table: str,
    filters: dict[str, list[str]] | None = None,
    sort_by: str | None = None,
    sort_dir: str = "asc",
    ttl: int = 3600,
    cache_source_name: str | None = None,
) -> list[dict[str, Any]]:
    filters = filters or {}
    effective_ttl = 0 if LOCAL_SQL else ttl
    source_name = cache_source_name or view_name
    key = cache_key(
        "tabular",
        view=source_name,
        filters={k: sorted(v) for k, v in sorted(filters.items())},
        sort_by=sort_by,
        sort_dir=sort_dir.lower(),
    )
    redis_client = get_redis_client()
    if effective_ttl > 0:
        cached = redis_client.get(key)
        if cached:
            data: list[dict[str, Any]] = json.loads(cached)
            return data

    query = build_view_query(
        view=view_name,
        filters=filters,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    data = execute_sql_query(query)
    payload = json.dumps(data, default=str)
    if effective_ttl > 0:
        cache_set(redis_client, key, source_name, data, effective_ttl)
    return data
