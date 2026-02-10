from fastapi import APIRouter, Depends, HTTPException
import redis
import json

from internal.auth import require_groups

redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)

router = APIRouter(
    prefix="/api/tables",
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

@router.get("/polcurve_view")
async def polcurve_view(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("polcurve_view")}

@router.get("/sample_overview")
async def sample_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("sample_overview")}

@router.get("/testrig_overview")
async def testrig_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("testrig_overview")}

@router.get("/timeseries_overview")
async def timeseries_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result("timeseries_overview")}