import json
import time

from fastapi import APIRouter, Depends, HTTPException

from backend.internal.auth import require_groups
from backend.internal.util import execute_sql_query, fully_qualified_view, get_redis_client, human_readable_bytes

import backend.config.sherlock as sherlock
import backend.config.watson as watson
import backend.config.enola as enola
import backend.config.mycroft as mycroft

router = APIRouter(prefix="/api/system", tags=["System"])

DEV_GROUP = "IdM2BCD_holmes_pemely_development"
STATS_CACHE_TTL_SECONDS = 3600
SAMPLE_ROWS = 200
STATS_CACHE_KEY = "holmes:system:table_stats:v1"


def _all_configured_views() -> list[tuple[str, str, str]]:
    """Return (space, data_kind, table_name) for every configured table across all spaces."""
    entries = []
    for space, mod in [("sherlock", sherlock), ("watson", watson), ("enola", enola), ("mycroft", mycroft)]:
        for cfg in mod.TABULAR_CONFIG:
            entries.append((space, "data", cfg.table_name))
        for cfg in mod.TIMESERIES_CONFIG:
            entries.append((space, "data", cfg.table_name))
        for cfg in mod.METADATA_CONFIG:
            entries.append((space, "metadata", cfg.table_name))
    return entries


def _estimate_avg_row_bytes(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    total = sum(len(json.dumps(row, default=str).encode()) for row in rows)
    return total / len(rows)


def _collect_view_stats(space: str, data_kind: str, table_name: str) -> dict:
    view_name = fully_qualified_view(space=space, data_kind=data_kind, table_name=table_name)
    try:
        row_count = int((execute_sql_query(f"SELECT COUNT(*) AS row_count FROM {view_name}") or [{}])[0].get("row_count", 0))
        sample_rows = execute_sql_query(f"SELECT * FROM {view_name} LIMIT {SAMPLE_ROWS}")
        column_count = len(sample_rows[0].keys()) if sample_rows else 0
        avg_row_bytes = _estimate_avg_row_bytes(sample_rows)
        estimated_total_bytes = int(row_count * avg_row_bytes)
        return {
            "space": space, "data_kind": data_kind, "table": table_name, "view": view_name,
            "row_count": row_count, "column_count": column_count,
            "sample_rows": len(sample_rows), "avg_row_bytes": round(avg_row_bytes, 2),
            "estimated_total_bytes": estimated_total_bytes,
            "estimated_total_size": human_readable_bytes(estimated_total_bytes),
            "status": "ok",
        }
    except Exception as exc:
        return {"space": space, "data_kind": data_kind, "table": table_name, "view": view_name, "status": "error", "error": str(exc)}


@router.get("/table-stats", summary="Benchmark all configured table views")
def get_table_stats(token: dict = Depends(require_groups([DEV_GROUP]))):
    _ = token
    r = get_redis_client()
    cached = r.get(STATS_CACHE_KEY)
    if cached:
        try:
            payload = json.loads(cached)
            payload["cache"] = "hit"
            return payload
        except json.JSONDecodeError:
            pass

    started_at = time.time()
    results = [_collect_view_stats(space, data_kind, table_name) for space, data_kind, table_name in _all_configured_views()]
    completed_at = time.time()

    ok_results = [r for r in results if r.get("status") == "ok"]
    total_bytes = sum(r.get("estimated_total_bytes", 0) for r in ok_results)
    payload = {
        "cache": "miss",
        "generated_at_utc": int(completed_at),
        "duration_seconds": round(completed_at - started_at, 2),
        "table_count": len(results),
        "ok_count": len(ok_results),
        "error_count": len(results) - len(ok_results),
        "estimated_total_bytes_all_tables": total_bytes,
        "estimated_total_size_all_tables": human_readable_bytes(total_bytes),
        "results": results,
    }
    try:
        r.set(STATS_CACHE_KEY, json.dumps(payload), ex=STATS_CACHE_TTL_SECONDS)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to cache table stats: {exc}")
    return payload
