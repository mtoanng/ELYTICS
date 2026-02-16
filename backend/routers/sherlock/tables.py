from fastapi import APIRouter, Depends, HTTPException
import redis
import json

from internal.auth import require_groups

redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)

router = APIRouter(
    prefix="/api/sherlock/tables",
    tags=["tables"],
)

def get_query_result(query_name):
    key = f"query_result:{query_name}"
    value = redis_client.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"No data found for {query_name}")
    try:
        return json.loads(value)  # Parse JSON string to Python list
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse data from Redis")

@router.get("/ccm_overview")
async def ccm_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("ccm_overview")}

@router.get("/order_overview")
async def order_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("order_overview")}

@router.get("/polcurve_view_data")
async def polcurve_view_data(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("polcurve_view_data")}

@router.get("/polcurve_view_meta")
async def polcurve_view_meta(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("polcurve_view_meta")}

@router.get("/sample_overview")
async def sample_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("sample_overview")}

@router.get("/testrig_activity_overview")
async def testrig_activity_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("testrig_activity_overview")}

@router.get("/testrig_statistics_overview")
async def testrig_statistics_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("testrig_statistics_overview")}

@router.get("/timeseries_exp_overview")
async def timeseries_exp_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("timeseries_exp_overview")}

@router.get("/timeseries_exp_raw_1s")
async def timeseries_exp_raw_1s(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("timeseries_exp_raw_1s")}
