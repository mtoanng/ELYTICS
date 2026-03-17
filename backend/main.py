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
from backend.internal.util import configure_redis_cache_policy, execute_sql_query, fully_qualified_view, get_redis_client, invalidate_view_cache

from backend.routers.tabular import router as tabular_router
from backend.routers.metadata import router as metadata_router
from backend.routers.timeseries import router as timeseries_router
from backend.routers.download import router as download_router
from backend.routers.system import router as system_router

import backend.config.sherlock as sherlock
import backend.config.watson as watson
import backend.config.enola as enola
import backend.config.mycroft as mycroft

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

CACHE_POLL_INTERVAL_SECONDS = int(os.getenv("CACHE_POLL_INTERVAL_SECONDS", "600"))

_SPACE_MODULES = [("sherlock", sherlock), ("watson", watson), ("enola", enola), ("mycroft", mycroft)]


def _all_views() -> list[str]:
    views: list[str] = []
    for space, mod in _SPACE_MODULES:
        for cfg in mod.TABULAR_CONFIG:
            views.append(fully_qualified_view(space, "data", cfg.table_name))
        for cfg in mod.TIMESERIES_CONFIG:
            views.append(fully_qualified_view(space, "data", cfg.table_name))
        for cfg in mod.METADATA_CONFIG:
            views.append(fully_qualified_view(space, "metadata", cfg.table_name))
    return list(dict.fromkeys(views))


async def _poll_table_versions() -> None:
    r = get_redis_client()
    while True:
        await asyncio.sleep(CACHE_POLL_INTERVAL_SECONDS)
        for view_name in _all_views():
            try:
                rows = execute_sql_query(f"DESCRIBE HISTORY {view_name} LIMIT 1")
                if not rows:
                    continue
                new_version = str(rows[0].get("version", ""))
                version_key = f"holmes:meta:version:{view_name}"
                stored = r.get(version_key)
                if stored != new_version:
                    invalidate_view_cache(view_name)
                    r.set(version_key, new_version)
                    logger.info("cache invalidated view=%s new_version=%s", view_name, new_version)
            except Exception:
                logger.exception("Failed to poll version for view=%s", view_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    for space, mod in _SPACE_MODULES:
        validate_space_configs(space, mod.TABULAR_CONFIG, mod.TIMESERIES_CONFIG, mod.METADATA_CONFIG)
    logger.info("config validation passed for all spaces")
    configure_redis_cache_policy()
    task = asyncio.create_task(_poll_table_versions())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)

Instrumentator().instrument(app).expose(app)

app.include_router(tabular_router)
app.include_router(metadata_router)
app.include_router(timeseries_router)
app.include_router(download_router)
app.include_router(system_router)

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
