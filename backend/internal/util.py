from fastapi import HTTPException
import redis
import json

redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)

def get_query_result(query_name):
    key = f"query_result:{query_name}"
    value = redis_client.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"No data found for {query_name}")
    try:
        return json.loads(value)  # Parse JSON string to Python list
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse data from Redis")

# dynamic route creation example

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any
import redis
import json

router = APIRouter()
r = redis.Redis(host="localhost", port=6379, db=0)  # configure as needed

BIG_TABLES = {"timeseries_exp_raw_1s", "polcurve_view_data"}
MAX_LIMIT = 5000

def create_table_route(table_name: str, required_filters: Optional[list] = None):
    """
    Generate a route for a table with filtering, pagination, and caching.
    """

    @router.get(f"/{table_name}")
    async def table_route(
        limit: int = Query(100, ge=1, le=MAX_LIMIT),
        offset: int = Query(0, ge=0),
        filters: Optional[Dict[str, Any]] = Depends(lambda: {}),
        token: Any = Depends(lambda: "auth_stub")  # replace with your auth
    ):
        # ensure required filters for big tables
        if table_name in BIG_TABLES:
            if required_filters:
                for f in required_filters:
                    if f not in filters:
                        raise HTTPException(
                            status_code=400,
                            detail=f"{f} filter is required for table {table_name}"
                        )

        # generate redis key
        key_parts = [table_name] + [f"{k}={v}" for k,v in (filters or {}).items()] + [f"limit={limit}", f"offset={offset}"]
        key = ":".join(key_parts)

        # check cache
        cached = r.get(key)
        if cached:
            return json.loads(cached)

        # build SQL with filters and pagination
        where_clause = " AND ".join([f"{k} = :{k}" for k in (filters or {})])
        sql = f"SELECT * FROM {table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        sql += f" LIMIT {limit} OFFSET {offset}"

        # execute query on Databricks
        data = get_query_result(table_name, filters=filters, limit=limit, offset=offset)  # you implement this

        # cache result (TTL 10min)
        r.set(key, json.dumps(data), ex=600)

        return {"data": data}

    return table_route


# example usage for each space:

TABLES = {
    "sample_overview": [],
    "timeseries_exp_raw_1s": ["experiment_id"],  # require experiment_id filter
    "order_overview": []
}

for table, required_filters in TABLES.items():
    create_table_route(table, required_filters)