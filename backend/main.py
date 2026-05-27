import asyncio
import logging
import os
from time import perf_counter
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parent / ".env")

from backend.services.auth import verify_oidc_token
from backend.config.types import validate_space_configs
from backend.services.cache import configure_redis_cache_policy
from backend.services.databricks import close_all_databricks_connections

from backend.routers.tabular import router as tabular_router
from backend.routers.metadata import router as metadata_router
from backend.routers.timeseries import router as timeseries_router

import backend.config.sherlock as sherlock
import backend.config.watson as watson
import backend.config.enola as enola
import backend.config.mycroft as mycroft

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

for _noisy in (
    "databricks.sql",
    "databricks.sql.auth",
    "databricks.sql.auth.retry",
    "databricks.sql.auth.thrift_http_client",
    "databricks.sql.session",
):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

for _noisy in ("uvicorn.access", "gunicorn.access"):
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


@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    started = perf_counter()
    status_code = 500
    response_bytes = -1
    try:
        response = await call_next(request)
        status_code = response.status_code
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                response_bytes = int(content_length)
            except ValueError:
                response_bytes = -1
        else:
            body = getattr(response, "body", None)
            if isinstance(body, (bytes, bytearray)):
                response_bytes = len(body)
        return response
    finally:
        elapsed_ms = (perf_counter() - started) * 1000
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%.2f response_bytes=%s",
            request.method,
            request.url.path,
            status_code,
            elapsed_ms,
            response_bytes,
        )

app.include_router(tabular_router)
app.include_router(metadata_router)
app.include_router(timeseries_router)

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
