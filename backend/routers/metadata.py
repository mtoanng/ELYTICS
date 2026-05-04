import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from backend.internal.auth import require_groups
from backend.internal.config_types import MetadataConfig
from backend.internal.metrics import record_query
from backend.internal.util import LOCAL_SQL, execute_sql_query, get_redis_client, resolve_query_source, _cache_set

import backend.config.sherlock as sherlock
import backend.config.watson as watson
import backend.config.enola as enola
import backend.config.mycroft as mycroft

router = APIRouter()
logger = logging.getLogger(__name__)

SPACE_METADATA_MAP: dict[str, list[MetadataConfig]] = {
    "sherlock": sherlock.METADATA_CONFIG,
    "watson":   watson.METADATA_CONFIG,
    "enola":    enola.METADATA_CONFIG,
    "mycroft":  mycroft.METADATA_CONFIG,
}


def _register_metadata_routes(space: str, configs: list[MetadataConfig]) -> None:
    for cfg in configs:
        _bind_route(space, cfg)


def _bind_route(space: str, cfg: MetadataConfig) -> None:
    def route_handler(token: dict = Depends(require_groups(cfg.auth_groups))):
        _ = token
        effective_ttl = 0 if LOCAL_SQL else cfg.ttl
        r = get_redis_client()
        try:
            query_source, cache_source = resolve_query_source(space=space, data_kind="metadata", table_name=cfg.table_name)
            cache_key = f"holmes:metadata:{cache_source}"
            if effective_ttl > 0:
                cached = r.get(cache_key)
                if cached:
                    record_query("metadata", space, cfg.table_name, cache_hit=True, duration_s=0, payload_bytes=len(cached), rows=0)
                    return {"data": json.loads(cached)}

            t0 = time.monotonic()
            data = execute_sql_query(f"SELECT DISTINCT * FROM {query_source}")
            duration = time.monotonic() - t0
            serialized = json.dumps(data, default=str)
            if effective_ttl > 0:
                _cache_set(r, cache_key, cache_source, data, effective_ttl)
            record_query("metadata", space, cfg.table_name, cache_hit=False, duration_s=duration, payload_bytes=len(serialized), rows=len(data))
            return {"data": data}
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("metadata query failed [space=%s table=%s]", space, cfg.table_name)
            raise HTTPException(status_code=500, detail=str(exc))

    router.add_api_route(
        path=f"/api/{space}/metadata/{cfg.route_name}",
        endpoint=route_handler,
        methods=["GET"],
        name=f"{space}_metadata_{cfg.route_name}",
        tags=[f"{space.title()} - Metadata"],
        summary=f"{space} metadata {cfg.route_name}",
    )


for _space, _configs in SPACE_METADATA_MAP.items():
    _register_metadata_routes(_space, _configs)
