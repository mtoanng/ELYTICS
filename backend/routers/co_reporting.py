import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.config.sherlock import _USER
from backend.services.auth import require_groups
from backend.services.co_reporting import (
    get_timeseries,
    list_channels,
    list_series_groups,
    query_timeseries_window,
)

router = APIRouter(prefix="/api/sherlock/co-reporting", tags=["Sherlock - CO Reporting"])
logger = logging.getLogger(__name__)


class COReportingQueryRequest(BaseModel):
    series: str
    uuid: str
    group: str
    channels: list[str] = Field(min_length=1)
    visible_start_s: float
    visible_end_s: float
    prefetch_margin_s: float | None = None
    resolution: Literal["auto", "raw", "agg", "agg1", "agg15", "agg60", "agg_1m", "agg_15m", "agg_60m"] = "auto"
    mode: str | None = None
    report_id: str | None = None
    include_band: bool | None = None


@router.get("/series")
def co_reporting_series(token: dict = Depends(require_groups(_USER))):
    _ = token
    try:
        return {"data": list_series_groups()}
    except Exception as exc:
        logger.exception("CO reporting series query failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/channels")
def co_reporting_channels(
    series: str = Query(...),
    uuid: str = Query(...),
    group: str = Query(...),
    token: dict = Depends(require_groups(_USER)),
):
    _ = token
    try:
        return {"data": list_channels(series=series, uuid=uuid, group=group)}
    except Exception as exc:
        logger.exception("CO reporting channel query failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/timeseries")
def co_reporting_timeseries(
    series: str = Query(...),
    uuid: str = Query(...),
    group: str = Query(...),
    channels: list[str] = Query(...),
    resolution: str = Query("agg", pattern="^(agg|raw)$"),
    token: dict = Depends(require_groups(_USER)),
):
    _ = token
    try:
        return {
            "data": get_timeseries(
                series=series,
                uuid=uuid,
                group=group,
                channels=channels,
                resolution=resolution,
            )
        }
    except Exception as exc:
        logger.exception("CO reporting timeseries query failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/query")
def co_reporting_query(
    request: COReportingQueryRequest,
    token: dict = Depends(require_groups(_USER)),
):
    _ = token
    try:
        return query_timeseries_window(
            series=request.series,
            uuid=request.uuid,
            group=request.group,
            channels=request.channels,
            visible_start_s=request.visible_start_s,
            visible_end_s=request.visible_end_s,
            prefetch_margin_s=request.prefetch_margin_s,
            resolution=request.resolution,
            mode=request.mode,
            report_id=request.report_id,
            include_band=request.include_band,
        )
    except Exception as exc:
        logger.exception("CO reporting window query failed")
        raise HTTPException(status_code=500, detail=str(exc))
