import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

load_dotenv(Path(__file__).resolve().parent / ".env")

from backend.internal.auth import verify_oidc_token
from backend.internal.config_types import validate_space_configs
from backend.internal.util import close_all_databricks_connections, configure_redis_cache_policy, execute_sql_query, fully_qualified_view, get_redis_client, invalidate_view_cache

from backend.routers.tabular import router as tabular_router
from backend.routers.metadata import router as metadata_router
from backend.routers.timeseries import router as timeseries_router
from backend.routers.download import router as download_router

import backend.config.sherlock as sherlock
import backend.config.watson as watson
import backend.config.enola as enola
import backend.config.mycroft as mycroft

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

for _noisy in ("databricks.sql", "databricks.sql.auth", "databricks.sql.auth.retry", "databricks.sql.auth.thrift_http_client"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

_SPACE_MODULES = [("sherlock", sherlock), ("watson", watson), ("enola", enola), ("mycroft", mycroft)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    for space, mod in _SPACE_MODULES:
        validate_space_configs(space, mod.TABULAR_CONFIG, mod.TIMESERIES_CONFIG, mod.METADATA_CONFIG)
    logger.info("config validation passed for all spaces")
    configure_redis_cache_policy()
    try:
        yield
    finally:
        close_all_databricks_connections()


app = FastAPI(lifespan=lifespan)

Instrumentator().instrument(app).expose(app)

app.include_router(tabular_router)
app.include_router(metadata_router)
app.include_router(timeseries_router)
app.include_router(download_router)

if os.getenv("ENVIRONMENT") == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/api/groups")
def get_user_groups(token: dict = Depends(verify_oidc_token)):
    user_groups = token.get("groups", [])
    holmes_groups = [g for g in user_groups if g.startswith("IdM2BCD_holmes_pemely_")]
    return {
        "user": token.get("email"),
        "holmes_groups": holmes_groups,
        "roles": token.get("roles", []),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
