from fastapi import APIRouter, Depends

from internal.auth import require_groups
from internal.util import get_query_result

SPACE = "sherlock"

router = APIRouter(
    prefix="/api/sherlock/tables",
    tags=["tables"],
)

@router.get("/ccm_overview")
async def ccm_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result(f"{SPACE}/ccm_overview")}

@router.get("/order_overview")
async def order_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result(f"{SPACE}/order_overview")}

@router.get("/polcurve_view_data")
async def polcurve_view_data(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result(f"{SPACE}/polcurve_view_data")}

@router.get("/polcurve_view_meta")
async def polcurve_view_meta(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result(f"{SPACE}/polcurve_view_meta")}

@router.get("/sample_overview")
async def sample_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result(f"{SPACE}/sample_overview")}

@router.get("/testrig_activity_overview")
async def testrig_activity_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result(f"{SPACE}/testrig_activity_overview")}

@router.get("/test_statistics")
async def test_statistics(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result(f"{SPACE}/test_statistics")}

@router.get("/timeseries_exp_overview")
async def timeseries_exp_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result(f"{SPACE}/timeseries_exp_overview")}

@router.get("/timeseries_exp_raw_1s")
async def timeseries_exp_raw_1s(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
    return {"data": get_query_result(f"{SPACE}/timeseries_exp_raw_1s")}
