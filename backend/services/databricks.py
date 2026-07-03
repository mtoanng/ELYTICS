import logging
import os
import threading
import warnings
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from backend.services.serialization import normalize_json_value

# Suppress deprecation warning from databricks-sql-connector about _user_agent_entry
warnings.filterwarnings("ignore", message=".*'_user_agent_entry'.*", category=DeprecationWarning)

logger = logging.getLogger(__name__)

DATABRICKS_SERVER_HOSTNAME = os.getenv("DATABRICKS_SERVER_HOSTNAME")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_AZURE_CLIENT_ID = os.getenv("DATABRICKS_AZURE_CLIENT_ID")
DATABRICKS_AZURE_CLIENT_SECRET = os.getenv("DATABRICKS_AZURE_CLIENT_SECRET")
DATABRICKS_AZURE_TENANT_ID = os.getenv("DATABRICKS_AZURE_TENANT_ID")
DATABRICKS_AZURE_WORKSPACE_RESOURCE_ID = os.getenv("DATABRICKS_AZURE_WORKSPACE_RESOURCE_ID")

_POOL_SIZE = int(os.getenv("DATABRICKS_POOL_SIZE", "4"))
_MAX_OVERFLOW = int(os.getenv("DATABRICKS_MAX_OVERFLOW", "1"))
_POOL_RECYCLE_SECONDS = int(os.getenv("DATABRICKS_POOL_RECYCLE_SECONDS", "3600"))
_AUTH_TYPE = os.getenv("DATABRICKS_AUTH_TYPE", "access-token").strip().lower()

_CONNECTION_LOCK = threading.Lock()
_ENGINE: Engine | None = None


def _build_engine() -> Engine:
    if not DATABRICKS_SERVER_HOSTNAME:
        raise RuntimeError("DATABRICKS_SERVER_HOSTNAME is not set")
    if not DATABRICKS_HTTP_PATH:
        raise RuntimeError("DATABRICKS_HTTP_PATH is not set")

    connect_args: dict[str, Any] = {
        "server_hostname": DATABRICKS_SERVER_HOSTNAME,
        "http_path": DATABRICKS_HTTP_PATH,
    }
    if _AUTH_TYPE == "databricks-oauth":
        connect_args["auth_type"] = "databricks-oauth"
    elif _AUTH_TYPE == "azure-sp-m2m":
        missing = [
            name
            for name, value in (
                ("DATABRICKS_AZURE_CLIENT_ID", DATABRICKS_AZURE_CLIENT_ID),
                ("DATABRICKS_AZURE_CLIENT_SECRET", DATABRICKS_AZURE_CLIENT_SECRET),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"{', '.join(missing)} must be set when DATABRICKS_AUTH_TYPE=azure-sp-m2m"
            )
        connect_args.update(
            {
                "auth_type": "azure-sp-m2m",
                "azure_client_id": DATABRICKS_AZURE_CLIENT_ID,
                "azure_client_secret": DATABRICKS_AZURE_CLIENT_SECRET,
            }
        )
        if DATABRICKS_AZURE_TENANT_ID:
            connect_args["azure_tenant_id"] = DATABRICKS_AZURE_TENANT_ID
        if DATABRICKS_AZURE_WORKSPACE_RESOURCE_ID:
            connect_args["azure_workspace_resource_id"] = DATABRICKS_AZURE_WORKSPACE_RESOURCE_ID
    else:
        if not DATABRICKS_TOKEN:
            raise RuntimeError(
                "DATABRICKS_TOKEN is not set (required unless DATABRICKS_AUTH_TYPE=databricks-oauth or azure-sp-m2m)"
            )
        connect_args["access_token"] = DATABRICKS_TOKEN

    return create_engine(
        "databricks://",
        connect_args=connect_args,
        pool_size=_POOL_SIZE,
        max_overflow=_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=_POOL_RECYCLE_SECONDS,
        future=True,
    )


def _get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        with _CONNECTION_LOCK:
            if _ENGINE is None:
                _ENGINE = _build_engine()
    return _ENGINE


def _dispose_engine() -> None:
    global _ENGINE
    with _CONNECTION_LOCK:
        engine = _ENGINE
        _ENGINE = None
    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            logger.debug("Failed to dispose Databricks SQLAlchemy engine", exc_info=True)


def close_all_databricks_connections() -> None:
    _dispose_engine()


def _should_reconnect(exc: Exception) -> bool:
    if isinstance(exc, DBAPIError):
        if exc.connection_invalidated:
            return True
        message = str(exc.orig).lower() if exc.orig else str(exc).lower()
    else:
        message = str(exc).lower()

    reconnect_markers = (
        "closed",
        "broken pipe",
        "connection reset",
        "connection aborted",
        "socket",
        "session",
        "transport",
        "eof",
        "timed out",
    )
    return any(marker in message for marker in reconnect_markers)


def execute_sql_query(query: str) -> list[dict[str, Any]]:
    for attempt in range(2):
        try:
            engine = _get_engine()
            with engine.connect() as connection:
                rows = connection.execute(text(query)).mappings().all()
            result: list[dict[str, Any]] = []
            for row in rows:
                normalized_row = {
                    str(col): normalize_json_value(value)
                    for col, value in row.items()
                }
                result.append(normalized_row)
            return result
        except (SQLAlchemyError, Exception) as exc:
            if attempt == 0 and _should_reconnect(exc):
                logger.warning(
                    "Databricks connection became unusable, reconnecting once"
                )
                _dispose_engine()
                continue
            raise
    raise RuntimeError("Databricks query execution failed after retry")
