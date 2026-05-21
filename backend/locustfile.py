import os
import random
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from locust import HttpUser, between, task

import backend.config.enola as enola
import backend.config.mycroft as mycroft
import backend.config.sherlock as sherlock
import backend.config.watson as watson

SPACE_CONFIG_MAP = {
    "sherlock": sherlock,
    "watson": watson,
    "enola": enola,
    "mycroft": mycroft,
}

TIMESERIES_FIELD_EXCLUDES = {
    "start",
    "end",
    "start_time",
    "end_time",
    "start_timestamp",
    "end_timestamp",
    "time_column",
    "target_points",
}


def _csv_env(name: str, default: str) -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_utc_ts(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _to_utc_z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class HolmesApiUser(HttpUser):
    """Locust user profile for TBP-HOLMES backend endpoints."""

    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        token = os.getenv("HOLMES_BEARER_TOKEN", "").strip()
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        # Allow testing with auth disabled via DISABLE_AUTH env var
        disable_auth = os.getenv("DISABLE_AUTH", "true").lower() == "true"
        self.auth_enabled = bool(token) or disable_auth

        print(
            f"[on_start] disable_auth={disable_auth}, token={'set' if token else 'not set'}, auth_enabled={self.auth_enabled}"
        )

        self.space = os.getenv("HOLMES_SPACE", "sherlock").strip().lower()
        self.fallback_order_id = os.getenv("HOLMES_ORDER_ID", "ELY2500085").strip()
        self.ts_time_column = os.getenv("HOLMES_TS_TIME_COLUMN", "time").strip()
        self.ts_columns_override = _csv_env("HOLMES_TIMESERIES_COLUMNS", "")
        self.ts_column_limit = max(1, int(os.getenv("HOLMES_TS_COLUMN_LIMIT", "6")))

        self.target_points_min = int(os.getenv("HOLMES_TARGET_POINTS_MIN", "600"))
        self.target_points_max = int(os.getenv("HOLMES_TARGET_POINTS_MAX", "1800"))

        default_ts_end = datetime.now(UTC)
        default_ts_start = default_ts_end - timedelta(days=365)
        self.ts_range_start = _parse_utc_ts(
            os.getenv("HOLMES_TS_RANGE_START", _to_utc_z(default_ts_start))
        )
        self.ts_range_end = _parse_utc_ts(
            os.getenv("HOLMES_TS_RANGE_END", _to_utc_z(default_ts_end))
        )
        self.ts_window_min_minutes = int(
            os.getenv("HOLMES_TS_WINDOW_MIN_MINUTES", "30")
        )
        self.ts_window_max_minutes = int(
            os.getenv("HOLMES_TS_WINDOW_MAX_MINUTES", "240")
        )

        self.order_ids: list[str] = _csv_env("HOLMES_ORDER_IDS", self.fallback_order_id)
        self.filter_pools: dict[str, list[str]] = {
            "order_id": list(self.order_ids),
            "testrig_id": _csv_env("HOLMES_TESTRIG_IDS", ""),
            "sample_name": _csv_env("HOLMES_SAMPLE_NAMES", ""),
            "number_of_cells": _csv_env("HOLMES_NUMBER_OF_CELLS", ""),
        }

        self.module = SPACE_CONFIG_MAP.get(self.space)
        if self.module is None:
            raise RuntimeError(f"Unknown HOLMES_SPACE: {self.space!r}")

        self.metadata_configs = list(getattr(self.module, "METADATA_CONFIG", []))
        self.tabular_configs = list(getattr(self.module, "TABULAR_CONFIG", []))
        self.timeseries_configs = list(getattr(self.module, "TIMESERIES_CONFIG", []))

        self.metadata_cache: dict[str, list[dict[str, Any]]] = {}
        self.required_filters_by_route = self._build_required_filters_by_route()

        print(
            f"[on_start] Loaded: {len(self.metadata_configs)} metadata, {len(self.tabular_configs)} tabular, {len(self.timeseries_configs)} timeseries configs"
        )

        if (
            self.auth_enabled
            and os.getenv("HOLMES_WARMUP_FILTERS_ON_START", "1") == "1"
        ):
            self._warmup_filter_pools()

    def _get(
        self,
        path: str,
        *,
        params: dict | Iterable[tuple[str, str]] | None = None,
        name: str | None = None,
    ) -> None:
        self.client.get(path, params=params, headers=self.headers, name=name or path)

    def _build_required_filters_by_route(self) -> dict[tuple[str, str], list[str]]:
        route_filters: dict[tuple[str, str], list[str]] = {}
        for cfg in self.tabular_configs:
            route_filters[("tabular", cfg.route_name)] = list(cfg.required_filters)
        for cfg in self.timeseries_configs:
            route_filters[("timeseries", cfg.route_name)] = list(cfg.required_filters)
        return route_filters

    def _extract_filter_values(
        self,
        rows: list[dict[str, Any]],
        required_keys: set[str],
    ) -> dict[str, set[str]]:
        extracted: dict[str, set[str]] = {key: set() for key in required_keys}
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key in required_keys:
                candidate = row.get(key)
                if candidate is None:
                    continue
                normalized = str(candidate).strip()
                if normalized:
                    extracted[key].add(normalized)
        return extracted

    def _warmup_filter_pools(self) -> None:
        required_keys = {
            key for keys in self.required_filters_by_route.values() for key in keys
        }
        if not required_keys:
            return

        discovered: dict[str, set[str]] = {
            key: set(self.filter_pools.get(key, [])) for key in required_keys
        }

        for cfg in self.metadata_configs:
            route_name = cfg.route_name
            path = f"/api/{self.space}/metadata/{route_name}"
            response = self.client.get(path, headers=self.headers)
            if response.status_code != 200:
                continue
            try:
                body = response.json()
            except ValueError:
                continue

            rows = body.get("data", [])
            if not isinstance(rows, list):
                continue

            self.metadata_cache[route_name] = [
                row for row in rows if isinstance(row, dict)
            ]
            extracted = self._extract_filter_values(
                self.metadata_cache[route_name], required_keys
            )
            for key, values in extracted.items():
                discovered[key].update(values)

        self.filter_pools.update(
            {
                key: [value for value in sorted(values) if value]
                for key, values in discovered.items()
            }
        )

        self.order_ids = list(self.filter_pools.get("order_id", []))
        if not self.order_ids:
            self.order_ids = [self.fallback_order_id]
            self.filter_pools["order_id"] = list(self.order_ids)

    def _random_filter_value(self, name: str, fallback: str = "") -> str:
        values = self.filter_pools.get(name, [])
        if values:
            return random.choice(values)
        return fallback

    def _required_filter_params(
        self, required_filters: list[str]
    ) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = []
        seen_any = False

        for key in required_filters:
            fallback = self.fallback_order_id if key == "order_id" else ""
            value = self._random_filter_value(key, fallback)
            if not value:
                continue
            params.append((key, value))
            seen_any = True

        if required_filters and not seen_any and "order_id" in required_filters:
            params.append(("order_id", self.fallback_order_id))

        return params

    def _random_timeseries_window(self) -> tuple[str, str]:
        start = self.ts_range_start
        end = self.ts_range_end
        if end <= start:
            start = _parse_utc_ts("2025-01-01T00:00:00Z")
            end = _parse_utc_ts("2025-01-02T00:00:00Z")

        total_seconds = int((end - start).total_seconds())
        min_seconds = max(60, self.ts_window_min_minutes * 60)
        max_seconds = max(min_seconds, self.ts_window_max_minutes * 60)
        max_seconds = min(max_seconds, total_seconds)

        if max_seconds <= min_seconds:
            window_seconds = min_seconds
        else:
            window_seconds = random.randint(min_seconds, max_seconds)

        latest_start_offset = max(0, total_seconds - window_seconds)
        start_offset = (
            random.randint(0, latest_start_offset) if latest_start_offset > 0 else 0
        )

        start_dt = start + timedelta(seconds=start_offset)
        end_dt = start_dt + timedelta(seconds=window_seconds)
        return _to_utc_z(start_dt), _to_utc_z(end_dt)

    def _random_target_points(self) -> str:
        low = min(self.target_points_min, self.target_points_max)
        high = max(self.target_points_min, self.target_points_max)
        return str(random.randint(low, high))

    def _infer_timeseries_columns(
        self, route_name: str, required_filters: list[str]
    ) -> list[str]:
        if self.ts_columns_override:
            return list(self.ts_columns_override)

        rows = self.metadata_cache.get(route_name, [])
        if not rows:
            return ["uCell", "jStck"]

        excluded = set(required_filters)
        excluded.update(TIMESERIES_FIELD_EXCLUDES)
        excluded.update({"order_id", "testrig_id", "sample_name", "number_of_cells"})

        columns: list[str] = []
        for key in rows[0].keys():
            if key in excluded:
                continue
            columns.append(str(key))

        if not columns:
            return ["uCell", "jStck"]
        return columns[: self.ts_column_limit]

    @task(1)
    def openapi(self) -> None:
        self._get("/openapi.json")

    @task(1)
    def docs(self) -> None:
        self._get("/docs")

    @task(2)
    def groups(self) -> None:
        if not self.auth_enabled:
            return
        self._get("/api/groups")

    @task(6)
    def metadata_request(self) -> None:
        if not self.auth_enabled:
            print("[metadata_request] Skipped: auth_enabled=False")
            return
        if not self.metadata_configs:
            print("[metadata_request] Skipped: no metadata_configs")
            return
        cfg = random.choice(self.metadata_configs)
        self._get(
            f"/api/{self.space}/metadata/{cfg.route_name}",
            name="/api/[space]/metadata/[route]",
        )

    @task(8)
    def tabular_request(self) -> None:
        if not self.auth_enabled or not self.tabular_configs:
            return

        cfg = random.choice(self.tabular_configs)
        required_params = self._required_filter_params(list(cfg.required_filters))
        if cfg.required_filters and not required_params:
            return

        params: list[tuple[str, str]] = list(required_params)
        params.append(("sort_dir", random.choice(["asc", "desc"])))

        self._get(
            f"/api/{self.space}/tabular/{cfg.route_name}",
            params=params,
            name="/api/[space]/tabular/[route]",
        )

    @task(6)
    def timeseries_request(self) -> None:
        if not self.auth_enabled or not self.timeseries_configs:
            return

        cfg = random.choice(self.timeseries_configs)
        required_params = self._required_filter_params(list(cfg.required_filters))
        if cfg.required_filters and not required_params:
            return

        start, end = self._random_timeseries_window()
        columns = self._infer_timeseries_columns(
            cfg.route_name, list(cfg.required_filters)
        )

        params: list[tuple[str, str]] = [
            ("start", start),
            ("end", end),
            ("time_column", self.ts_time_column),
            ("target_points", self._random_target_points()),
        ]
        params.extend(required_params)
        params.extend(("columns", col) for col in columns)

        self._get(
            f"/api/{self.space}/timeseries/{cfg.route_name}",
            params=params,
            name="/api/[space]/timeseries/[route]",
        )
