from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.internal.auth import require_groups
from backend.internal.config_types import TabularConfig
from backend.internal.util import fully_qualified_view, get_query_result

import backend.config.sherlock as sherlock
import backend.config.watson as watson
import backend.config.enola as enola
import backend.config.mycroft as mycroft

router = APIRouter()

SPACE_TABULAR_MAP: dict[str, list[TabularConfig]] = {
    "sherlock": sherlock.TABULAR_CONFIG,
    "watson":   watson.TABULAR_CONFIG,
    "enola":    enola.TABULAR_CONFIG,
    "mycroft":  mycroft.TABULAR_CONFIG,
}


def _parse_filters(request: Request) -> dict[str, list[str]]:
    excluded = {"limit", "offset", "sort_by", "sort_dir"}
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
        limit: int = Query(100, ge=1, le=cfg.max_limit),
        offset: int = Query(0, ge=0),
        sort_by: str | None = Query(None),
        sort_dir: str = Query("asc"),
        token: dict = Depends(require_groups(cfg.auth_groups)),
    ):
        _ = token
        if sort_dir.lower() not in {"asc", "desc"}:
            raise HTTPException(status_code=400, detail="sort_dir must be 'asc' or 'desc'")
        filters = _parse_filters(request)
        for required in cfg.required_filters:
            if required not in filters:
                raise HTTPException(status_code=400, detail=f"Missing required filter '{required}'")
        view_name = fully_qualified_view(space=space, data_kind="data", table_name=cfg.table_name)
        data = get_query_result(
            view_name=view_name,
            space=space,
            table=cfg.table_name,
            filters=filters,
            sort_by=sort_by,
            sort_dir=sort_dir.lower(),
            limit=limit,
            offset=offset,
            ttl=cfg.ttl,
        )
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
