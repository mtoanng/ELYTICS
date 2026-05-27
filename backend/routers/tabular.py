import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.services.auth import require_groups
from backend.config.types import TabularConfig
from backend.services.sql import get_query_result, resolve_query_source

import backend.config.sherlock as sherlock
import backend.config.watson as watson
import backend.config.enola as enola
import backend.config.mycroft as mycroft

router = APIRouter()
logger = logging.getLogger(__name__)

SPACE_TABULAR_MAP: dict[str, list[TabularConfig]] = {
    "sherlock": sherlock.TABULAR_CONFIG,
    "watson":   watson.TABULAR_CONFIG,
    "enola":    enola.TABULAR_CONFIG,
    "mycroft":  mycroft.TABULAR_CONFIG,
}


def _parse_filters(request: Request) -> dict[str, list[str]]:
    excluded = {"sort_by", "sort_dir"}
    parsed: dict[str, list[str]] = defaultdict(list)
    for key, value in request.query_params.multi_items():
        if key not in excluded:
            parsed[key].append(value)
    return dict(parsed)


def _register_tabular_routes(space: str, configs: list[TabularConfig]) -> None:
    for cfg in configs:
        _bind_route(space, cfg)


def _bind_route(space: str, cfg: TabularConfig) -> None:
    def route_handler(
        request: Request,
        sort_by: str | None = Query(None),
        sort_dir: str = Query("asc"),
        token: dict = Depends(require_groups(cfg.auth_groups)),
    ):
        _ = token
        if sort_dir.lower() not in {"asc", "desc"}:
            raise HTTPException(status_code=400, detail="sort_dir must be 'asc' or 'desc'")
        filters = _parse_filters(request)
        if cfg.required_filters:  # If there are any required filters
            if not any(required in filters for required in cfg.required_filters):
                raise HTTPException(
                    status_code=400, 
                    detail=f"At least one of these filters is required: {', '.join(cfg.required_filters)}"
                )        
        try:
            query_source, cache_source = resolve_query_source(space=space, data_kind="data", table_name=cfg.table_name)
            data = get_query_result(
                view_name=query_source,
                space=space,
                table=cfg.table_name,
                filters=filters,
                sort_by=sort_by,
                sort_dir=sort_dir.lower(),
                ttl=cfg.ttl,
                cache_source_name=cache_source,
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("tabular query failed [space=%s table=%s]", space, cfg.table_name)
            raise HTTPException(status_code=500, detail=str(exc))
        return {"data": data}

    router.add_api_route(
        path=f"/api/{space}/tabular/{cfg.route_name}",
        endpoint=route_handler,
        methods=["GET"],
        name=f"{space}_tabular_{cfg.route_name}",
        tags=[f"{space.title()} - Tabular"],
        summary=f"{space} tabular {cfg.route_name}",
    )


for _space, _configs in SPACE_TABULAR_MAP.items():
    _register_tabular_routes(_space, _configs)
