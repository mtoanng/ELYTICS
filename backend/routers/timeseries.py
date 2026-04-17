from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.internal.auth import require_groups
from backend.internal.config_types import TimeseriesConfig
from backend.internal.util import _TARGET_POINTS_DEFAULT, fully_qualified_view, get_timeseries_result

import backend.config.sherlock as sherlock
import backend.config.watson as watson
import backend.config.enola as enola
import backend.config.mycroft as mycroft

router = APIRouter()

SPACE_TIMESERIES_MAP: dict[str, list[TimeseriesConfig]] = {
    "sherlock": sherlock.TIMESERIES_CONFIG,
    "watson":   watson.TIMESERIES_CONFIG,
    "enola":    enola.TIMESERIES_CONFIG,
    "mycroft":  mycroft.TIMESERIES_CONFIG,
}


def _parse_filters(request: Request) -> dict[str, list[str]]:
    excluded = {"start", "end", "columns", "target_points", "time_column"}
    parsed: dict[str, list[str]] = defaultdict(list)
    for key, value in request.query_params.multi_items():
        if key not in excluded:
            parsed[key].append(value)
    return dict(parsed)


def _register_timeseries_routes(space: str, configs: list[TimeseriesConfig]) -> None:
    for cfg in configs:
        _bind_route(space, cfg)


def _bind_route(space: str, cfg: TimeseriesConfig) -> None:
    async def route_handler(
        request: Request,
        start: datetime | None = Query(None),
        end: datetime | None = Query(None),
        columns: list[str] = Query(...),
        time_column: str = Query(...),
        target_points: int = Query(_TARGET_POINTS_DEFAULT),
        token: dict = Depends(require_groups(cfg.auth_groups)),
    ):
        _ = token
        filters = _parse_filters(request)
        for required in cfg.required_filters:
            if required not in filters:
                raise HTTPException(status_code=400, detail=f"Missing required filter '{required}'")
        view_name = fully_qualified_view(space=space, data_kind="data", table_name=cfg.table_name)
        try:
            payload = get_timeseries_result(
                view_name=view_name,
                space=space,
                table=cfg.table_name,
                time_column=time_column,
                value_columns=columns,
                start_time=start,
                end_time=end,
                filters=filters,
                target_points=target_points,
                ttl=cfg.ttl,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return payload

    router.add_api_route(
        path=f"/api/{space}/timeseries/{cfg.route_name}",
        endpoint=route_handler,
        methods=["GET"],
        name=f"{space}_timeseries_{cfg.route_name}",
        tags=[f"{space.title()} - Timeseries"],
        summary=f"{space} timeseries {cfg.route_name}",
    )


for _space, _configs in SPACE_TIMESERIES_MAP.items():
    _register_timeseries_routes(_space, _configs)
