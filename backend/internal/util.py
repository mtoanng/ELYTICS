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
