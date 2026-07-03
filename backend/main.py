import logging
import os
from time import perf_counter
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parent / ".env")

from backend.services.cache import configure_redis_cache_policy
from backend.services.databricks import close_all_databricks_connections

from backend.routers.co_reporting import router as co_reporting_router

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

@asynccontextmanager
async def lifespan(app: FastAPI):
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

app.include_router(co_reporting_router)

if os.getenv("ENVIRONMENT") == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
