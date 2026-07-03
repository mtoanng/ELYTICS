import hashlib
import json
import os
from typing import Any

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

_redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True,
    max_connections=20,
)


def get_redis_client() -> redis.Redis:
    return redis.Redis(connection_pool=_redis_pool)


def configure_redis_cache_policy(max_memory_bytes: int = 2 * 1024 * 1024 * 1024) -> None:
    client = get_redis_client()
    try:
        client.config_set("maxmemory", max_memory_bytes)
        client.config_set("maxmemory-policy", "allkeys-lru")
    except redis.RedisError:
        pass


def cache_key(prefix: str, **kwargs: Any) -> str:
    digest = hashlib.sha256(
        json.dumps(kwargs, sort_keys=True, default=str).encode()
    ).hexdigest()
    return f"elytics:{prefix}:{digest}"


def cache_set(
    redis_client: redis.Redis,
    key: str,
    source_name: str,
    payload: Any,
    ttl: int,
) -> None:
    redis_client.set(key, json.dumps(payload, default=str), ex=ttl)
    redis_client.sadd(f"elytics:index:{source_name}", key)


def invalidate_source_cache(source_name: str) -> None:
    redis_client = get_redis_client()
    index_key = f"elytics:index:{source_name}"
    keys = redis_client.smembers(index_key)
    if keys:
        redis_client.delete(*keys)
    redis_client.delete(index_key)


def human_readable_bytes(num_bytes: float) -> str:
    value = float(max(num_bytes, 0))
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    return f"{int(value)} {units[idx]}" if idx == 0 else f"{value:.2f} {units[idx]}"
