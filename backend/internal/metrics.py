from prometheus_client import Counter, Histogram

CACHE_HITS = Counter(
    "holmes_cache_hits_total",
    "Number of Redis cache hits",
    ["query_type", "space", "table"],
)
CACHE_MISSES = Counter(
    "holmes_cache_misses_total",
    "Number of Redis cache misses",
    ["query_type", "space", "table"],
)
QUERY_DURATION = Histogram(
    "holmes_query_duration_seconds",
    "Databricks query duration in seconds",
    ["query_type", "space", "table"],
)
PAYLOAD_SIZE_BYTES = Histogram(
    "holmes_payload_size_bytes",
    "Response payload size in bytes",
    ["query_type", "space", "table"],
    buckets=[1_000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000],
)
ROWS_RETURNED = Counter(
    "holmes_rows_returned_total",
    "Total number of rows returned from Databricks",
    ["query_type", "space", "table"],
)


def record_query(
    query_type: str,
    space: str,
    table: str,
    cache_hit: bool,
    duration_s: float,
    payload_bytes: int,
    rows: int,
) -> None:
    labels = {"query_type": query_type, "space": space, "table": table}
    if cache_hit:
        CACHE_HITS.labels(**labels).inc()
    else:
        CACHE_MISSES.labels(**labels).inc()
        QUERY_DURATION.labels(**labels).observe(duration_s)
        PAYLOAD_SIZE_BYTES.labels(**labels).observe(payload_bytes)
        ROWS_RETURNED.labels(**labels).inc(rows)
