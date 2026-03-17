import os
import random
from datetime import UTC, datetime, timedelta
from typing import Iterable

from locust import HttpUser, between, task


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
        self.auth_enabled = bool(token)

        self.space = os.getenv("HOLMES_SPACE", "sherlock")
        self.fallback_order_id = os.getenv("HOLMES_ORDER_ID", "ELY2500085")
        self.ts_time_column = os.getenv("HOLMES_TS_TIME_COLUMN", "time")
        self.ts_columns = _csv_env("HOLMES_TIMESERIES_COLUMNS", "uCell,jStck")
        self.include_system_stats = os.getenv("HOLMES_INCLUDE_SYSTEM_STATS", "0") == "1"
        self.enable_download = os.getenv("HOLMES_ENABLE_DOWNLOAD", "0") == "1"

        self.limit_min = int(os.getenv("HOLMES_LIMIT_MIN", "50"))
        self.limit_max = int(os.getenv("HOLMES_LIMIT_MAX", "250"))
        self.offset_max = int(os.getenv("HOLMES_OFFSET_MAX", "1000"))

        self.target_points_min = int(os.getenv("HOLMES_TARGET_POINTS_MIN", "600"))
        self.target_points_max = int(os.getenv("HOLMES_TARGET_POINTS_MAX", "1800"))

        self.ts_range_start = _parse_utc_ts(os.getenv("HOLMES_TS_RANGE_START", "2024-01-01T00:00:00Z"))
        self.ts_range_end = _parse_utc_ts(os.getenv("HOLMES_TS_RANGE_END", "2026-01-01T00:00:00Z"))
        self.ts_window_min_minutes = int(os.getenv("HOLMES_TS_WINDOW_MIN_MINUTES", "30"))
        self.ts_window_max_minutes = int(os.getenv("HOLMES_TS_WINDOW_MAX_MINUTES", "240"))

        self.order_ids: list[str] = _csv_env("HOLMES_ORDER_IDS", self.fallback_order_id)
        if self.auth_enabled and os.getenv("HOLMES_WARMUP_FILTERS_ON_START", "1") == "1":
            self._warmup_filter_pools()

    def _get(self, path: str, *, params: dict | Iterable[tuple[str, str]] | None = None, name: str | None = None) -> None:
        self.client.get(path, params=params, headers=self.headers, name=name or path)

    def _post(self, path: str, *, params: dict | None = None, name: str | None = None) -> None:
        self.client.post(path, params=params, headers=self.headers, name=name or path)

    def _extract_order_ids(self, body: dict) -> list[str]:
        values: list[str] = []
        for row in body.get("data", []):
            if not isinstance(row, dict):
                continue
            candidate = row.get("order_id")
            if candidate is not None and str(candidate).strip():
                values.append(str(candidate).strip())
        return values

    def _warmup_filter_pools(self) -> None:
        candidates: set[str] = set(self.order_ids)

        for path in (
            f"/api/{self.space}/metadata/timeseries_exp",
            f"/api/{self.space}/metadata/polcurve",
            f"/api/{self.space}/tabular/order",
        ):
            response = self.client.get(path, headers=self.headers, params={"limit": 500, "offset": 0})
            if response.status_code != 200:
                continue
            try:
                body = response.json()
            except ValueError:
                continue
            candidates.update(self._extract_order_ids(body))

        self.order_ids = [v for v in sorted(candidates) if v]
        if not self.order_ids:
            self.order_ids = [self.fallback_order_id]

    def _random_order_id(self) -> str:
        if not self.order_ids:
            return self.fallback_order_id
        return random.choice(self.order_ids)

    def _random_limit(self) -> int:
        if self.limit_max <= self.limit_min:
            return self.limit_min
        return random.randint(self.limit_min, self.limit_max)

    def _random_offset(self) -> int:
        return random.randint(0, max(0, self.offset_max))

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
        start_offset = random.randint(0, latest_start_offset) if latest_start_offset > 0 else 0

        start_dt = start + timedelta(seconds=start_offset)
        end_dt = start_dt + timedelta(seconds=window_seconds)
        return _to_utc_z(start_dt), _to_utc_z(end_dt)

    def _random_target_points(self) -> str:
        low = min(self.target_points_min, self.target_points_max)
        high = max(self.target_points_min, self.target_points_max)
        return str(random.randint(low, high))

    @task(1)
    def openapi(self) -> None:
        self._get("/openapi.json")

    @task(1)
    def metrics(self) -> None:
        self._get("/metrics")

    @task(2)
    def docs(self) -> None:
        self._get("/docs")

    @task(3)
    def groups(self) -> None:
        if not self.auth_enabled:
            return
        self._get("/api/groups")

    @task(6)
    def metadata_polcurve(self) -> None:
        if not self.auth_enabled:
            return
        self._get(f"/api/{self.space}/metadata/polcurve")

    @task(6)
    def tabular_order(self) -> None:
        if not self.auth_enabled:
            return
        self._get(
            f"/api/{self.space}/tabular/order",
            params={
                "limit": self._random_limit(),
                "offset": self._random_offset(),
                "sort_dir": random.choice(["asc", "desc"]),
            },
            name="/api/[space]/tabular/order",
        )

    @task(4)
    def tabular_track_record(self) -> None:
        if not self.auth_enabled:
            return
        order_id = self._random_order_id()
        self._get(
            f"/api/{self.space}/tabular/track_record",
            params={"order_id": order_id, "limit": self._random_limit(), "offset": self._random_offset()},
            name="/api/[space]/tabular/track_record",
        )

    @task(4)
    def tabular_polcurve(self) -> None:
        if not self.auth_enabled:
            return
        order_id = self._random_order_id()
        self._get(
            f"/api/{self.space}/tabular/polcurve",
            params={"order_id": order_id, "limit": self._random_limit(), "offset": self._random_offset()},
            name="/api/[space]/tabular/polcurve",
        )

    @task(4)
    def timeseries_exp(self) -> None:
        if not self.auth_enabled:
            return
        start, end = self._random_timeseries_window()
        params: list[tuple[str, str]] = [
            ("start", start),
            ("end", end),
            ("time_column", self.ts_time_column),
            ("order_id", self._random_order_id()),
            ("target_points", self._random_target_points()),
        ]
        params.extend(("columns", col) for col in self.ts_columns)
        self._get(
            f"/api/{self.space}/timeseries/timeseries_exp",
            params=params,
            name="/api/[space]/timeseries/timeseries_exp",
        )

    @task(2)
    def metadata_timeseries(self) -> None:
        if not self.auth_enabled:
            return
        self._get(f"/api/{self.space}/metadata/timeseries_exp")

    @task(2)
    def metadata_polcurve_vlite(self) -> None:
        if not self.auth_enabled:
            return
        self._get(f"/api/{self.space}/metadata/polcurve_vlite")

    @task(1)
    def tabular_polcurve_vlite(self) -> None:
        if not self.auth_enabled:
            return
        order_id = self._random_order_id()
        self._get(
            f"/api/{self.space}/tabular/polcurve_vlite",
            params={"order_id": order_id, "limit": self._random_limit(), "offset": self._random_offset()},
            name="/api/[space]/tabular/polcurve_vlite",
        )

    @task(1)
    def tabular_sample(self) -> None:
        if not self.auth_enabled:
            return
        self._get(
            f"/api/{self.space}/tabular/sample",
            params={"limit": self._random_limit(), "offset": self._random_offset()},
            name="/api/[space]/tabular/sample",
        )

    @task(1)
    def tabular_ccm(self) -> None:
        if not self.auth_enabled:
            return
        self._get(
            f"/api/{self.space}/tabular/ccm",
            params={"limit": self._random_limit(), "offset": self._random_offset()},
            name="/api/[space]/tabular/ccm",
        )

    @task(1)
    def tabular_testrig_activity(self) -> None:
        if not self.auth_enabled:
            return
        self._get(
            f"/api/{self.space}/tabular/testrig_activity",
            params={"limit": self._random_limit(), "offset": self._random_offset()},
            name="/api/[space]/tabular/testrig_activity",
        )

    @task(1)
    def tabular_testrig_statistics(self) -> None:
        if not self.auth_enabled:
            return
        self._get(
            f"/api/{self.space}/tabular/testrig_statistics",
            params={"limit": self._random_limit(), "offset": self._random_offset()},
            name="/api/[space]/tabular/testrig_statistics",
        )

    @task(1)
    def tabular_soh(self) -> None:
        if not self.auth_enabled:
            return
        self._get(
            f"/api/{self.space}/tabular/soh",
            params={"limit": self._random_limit(), "offset": self._random_offset()},
            name="/api/[space]/tabular/soh",
        )