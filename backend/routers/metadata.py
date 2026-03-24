import json
import time

from fastapi import APIRouter, Depends, HTTPException

from backend.internal.auth import require_groups
from backend.internal.config_types import MetadataConfig
from backend.internal.metrics import record_query
from backend.internal.util import execute_sql_query, fully_qualified_view, get_redis_client, _cache_set

import backend.config.sherlock as sherlock
import backend.config.watson as watson
import backend.config.enola as enola
import backend.config.mycroft as mycroft

router = APIRouter()

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
        view_name = fully_qualified_view(space=space, data_kind="metadata", table_name=cfg.table_name)
        cache_key = f"holmes:metadata:{view_name}"
        r = get_redis_client()
        cached = r.get(cache_key)
        if cached:
            record_query("metadata", space, cfg.table_name, cache_hit=True, duration_s=0, payload_bytes=len(cached), rows=0)
            return {"data": json.loads(cached)}

        t0 = time.monotonic()
        try:
            data = execute_sql_query(f"SELECT DISTINCT * FROM {view_name}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        duration = time.monotonic() - t0
        serialized = json.dumps(data, default=str)
        _cache_set(r, cache_key, view_name, data, cfg.ttl)
        record_query("metadata", space, cfg.table_name, cache_hit=False, duration_s=duration, payload_bytes=len(serialized), rows=len(data))
        return {"data": data}

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
