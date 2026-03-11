import json
import os
import time

from fastapi import APIRouter, Depends, HTTPException

from internal.auth import require_groups
from internal.util import execute_sql_query, fully_qualified_view, get_redis_client, human_readable_bytes
from routers.tables import SPACE_TABLE_MAP

router = APIRouter(prefix="/api/system", tags=["System"])

DEV_GROUP = "IdM2BCD_holmes_pemely_development"
STATS_CACHE_TTL_SECONDS = int(os.getenv("SYSTEM_TABLE_STATS_TTL_SECONDS", "3600"))
SAMPLE_ROWS = int(os.getenv("SYSTEM_TABLE_STATS_SAMPLE_ROWS", "200"))
STATS_CACHE_KEY = "holmes:system:table_stats:v1"


def _estimate_avg_row_bytes(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    total = 0
    for row in rows:
        total += len(json.dumps(row, default=str).encode("utf-8"))
    return total / len(rows)


def _collect_view_stats(space: str, data_kind: str, table_name: str) -> dict:
    view_name = fully_qualified_view(space=space, data_kind=data_kind, table_name=table_name)

    try:
        row_count_query = f"SELECT COUNT(*) AS row_count FROM {view_name}"
        row_count_result = execute_sql_query(row_count_query)
        row_count = int(row_count_result[0].get("row_count", 0)) if row_count_result else 0

        sample_query = f"SELECT * FROM {view_name} LIMIT {SAMPLE_ROWS}"
        sample_rows = execute_sql_query(sample_query)
        column_count = len(sample_rows[0].keys()) if sample_rows else 0
        avg_row_bytes = _estimate_avg_row_bytes(sample_rows)
        estimated_total_bytes = int(row_count * avg_row_bytes)

        return {
            "space": space,
            "data_kind": data_kind,
            "table": table_name,
            "view": view_name,
            "row_count": row_count,
            "column_count": column_count,
            "sample_rows": len(sample_rows),
            "avg_row_bytes": round(avg_row_bytes, 2),
            "estimated_total_bytes": estimated_total_bytes,
            "estimated_total_size": human_readable_bytes(estimated_total_bytes),
            "status": "ok",
        }
    except Exception as exc:
        return {
            "space": space,
            "data_kind": data_kind,
            "table": table_name,
            "view": view_name,
            "status": "error",
            "error": str(exc),
        }


@router.get("/table-stats", summary="Benchmark all configured table views")
def get_table_stats(token: dict = Depends(require_groups([DEV_GROUP]))):
    _ = token

    redis_client = get_redis_client()
    cached = redis_client.get(STATS_CACHE_KEY)
    if cached:
        try:
            payload = json.loads(cached)
            payload["cache"] = "hit"
            return payload
        except json.JSONDecodeError:
            pass

    started_at = time.time()
    results: list[dict] = []

    for space, kind_map in SPACE_TABLE_MAP.items():
        for data_kind, tables in kind_map.items():
            for table_name in tables:
                results.append(_collect_view_stats(space=space, data_kind=data_kind, table_name=table_name))

    completed_at = time.time()
    ok_results = [r for r in results if r.get("status") == "ok"]
    total_estimated_bytes = sum(r.get("estimated_total_bytes", 0) for r in ok_results)

    payload = {
        "cache": "miss",
        "generated_at_utc": int(completed_at),
        "duration_seconds": round(completed_at - started_at, 2),
        "table_count": len(results),
        "ok_count": len(ok_results),
        "error_count": len(results) - len(ok_results),
        "estimated_total_bytes_all_tables": total_estimated_bytes,
        "estimated_total_size_all_tables": human_readable_bytes(total_estimated_bytes),
        "results": results,
    }

    try:
        redis_client.set(STATS_CACHE_KEY, json.dumps(payload), ex=STATS_CACHE_TTL_SECONDS)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to cache table stats in Redis: {exc}")

    return payload
