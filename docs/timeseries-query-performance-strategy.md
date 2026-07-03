# Timeseries Query Performance Strategy

## Context

The HOLMES application visualizes large Databricks-backed timeseries datasets through a FastAPI backend and a Dash frontend. The current Sherlock timeseries page requests bucketed data from the backend, stores the returned rows in Dash state, and renders both a main chart and a normalized chart.

The current performance symptom is severe latency for dashboard visualizations, even with Redis caching enabled. This document explains why Redis alone does not solve the problem and proposes technical improvements at both implementation and architecture levels.

## Current Request Path

For the Sherlock timeseries overview, the typical path is:

1. Dash callback calls `frontend/services/backend_service.py:get_timeseries()`.
2. Frontend sends an HTTP GET request to `/api/sherlock/timeseries/timeseries_exp`.
3. FastAPI route in `backend/routers/timeseries.py` calls `get_timeseries_result()`.
4. Backend resolves time bounds, computes a bucket size, and builds SQL dynamically.
5. Backend checks Redis for a cached JSON payload.
6. On cache miss, backend queries Databricks SQL through SQLAlchemy.
7. Databricks rows are materialized into Python dictionaries.
8. Backend serializes the payload to JSON and stores it in Redis.
9. FastAPI serializes the response to JSON again for HTTP.
10. Frontend parses JSON and converts rows into a pandas DataFrame.
11. Frontend converts the DataFrame back into `records` for `dcc.Store`.
12. Separate Dash callbacks rebuild pandas DataFrames from those records.
13. Plotly builds the main timeseries figure and the normalized figure.
14. Dash serializes the generated figures back to the browser.

This is not just a Databricks query problem. The path includes repeated data conversion, JSON serialization, network transfer, Dash state transfer, and browser rendering.

## Why The Current App Query Is Slow

### 1. Redis Caches Large JSON Strings, Not Query-Ready Data

`backend/services/cache.py` configures Redis with `decode_responses=True`, so Redis returns Python strings rather than bytes. The cache setter serializes the full payload:

```python
redis_client.set(key, json.dumps(payload, default=str), ex=ttl)
```

A cache hit still performs:

- Redis string read
- Python memory allocation for the full JSON string
- `json.loads()` into Python objects
- FastAPI JSON serialization for the response
- frontend `response.json()` parsing
- pandas DataFrame creation

Redis avoids the Databricks query on cache hits, but it does not avoid most of the serialization and object-construction cost.

For large chart payloads, Redis can become a large JSON blob store. That is a poor fit for high-volume timeseries visualization.

### 2. Databricks Results Are Fully Materialized In Python

`backend/services/databricks.py` uses:

```python
rows = connection.execute(text(query)).mappings().all()
```

This materializes the full result set in backend memory before returning anything. Then each value is normalized into plain JSON-compatible Python values.

That means cache misses pay for:

- Databricks SQL execution
- full result materialization
- per-cell Python normalization
- dictionary creation for every row
- JSON serialization

For chart data, this row-by-row Python path can be a major bottleneck.

### 3. Dynamic Aggregation Happens During User Requests

`backend/services/timeseries.py` builds a query like:

```sql
SELECT
  bucket_start,
  MIN(signal),
  MAX(signal),
  AVG(signal)
FROM view
WHERE ...
GROUP BY bucket_start
ORDER BY bucket_start
```

The backend computes a bucket size, but the aggregation still happens at request time against the Databricks view.

This is acceptable for occasional ad hoc exploration. It is not ideal for dashboards that users load repeatedly with common filters and time windows.

For hot dashboard paths, the application should query pre-aggregated serving tables instead of grouping the large source table on demand.

### 4. The Cache Key Can Fragment Heavily

The timeseries cache key includes:

- view name
- time column
- sorted value columns
- filters
- effective start time
- effective end time
- bucket seconds

This is correct for accuracy, but it means small differences in time range, selected filters, selected signals, or bucket size create different Redis keys.

Interactive dashboards can therefore have low cache hit rates, especially after zooming, changing filters, or selecting extra signals.

### 5. The Frontend Re-serializes Data Through Dash State

In `frontend/spaces/sherlock/explore/timeseries_overview.py`, `load_timeseries_data()` converts the response into a DataFrame and then returns:

```python
"records": plot_df.to_dict("records")
```

Those records are stored in `dcc.Store`. Later callbacks convert those records back into pandas DataFrames to build figures.

This causes repeated conversion:

```text
JSON -> pandas DataFrame -> list[dict] -> Dash JSON -> pandas DataFrame -> Plotly figure JSON
```

For small responses this is fine. For large chart responses this becomes expensive.

### 6. Two Figures Are Built From The Same Data

The Sherlock page builds both:

- a main isolated timeseries chart
- a normalized comparison chart

This is useful, and it avoids two backend timeseries calls. But it still doubles some frontend processing and Plotly figure-building work.

If the stored records are large, rendering can dominate the user-visible latency even after the backend response has arrived.

### 7. Response Compression Is Not Enabled

`backend/main.py` logs request timing and response bytes, but it does not enable FastAPI `GZipMiddleware` or Brotli compression.

Large JSON chart payloads compress well. Without compression, network transfer can become a major part of total latency.

Compression will not fix excessive point counts, but it is a straightforward improvement for large JSON responses.

### 8. Redis Appears Shared Between Backend Cache And Frontend Sessions

The backend cache defaults to Redis database `0`.

The frontend Flask session store also defaults to Redis database `0`.

Sharing the same Redis DB for sessions and query cache can cause:

- memory pressure
- key eviction competition
- noisier performance characteristics
- harder debugging

These workloads should be separated.

### 9. Network Transfer May Be A Symptom, Not The Root Cause

Network transfer can absolutely be a bottleneck, especially if the backend sends large JSON responses. But the root issue is usually that too much data is being moved through too many layers.

The best fix is to reduce the payload before it reaches the network:

- pre-aggregate
- choose an appropriate grain
- limit returned points
- avoid sending raw/high-resolution data unless the viewport is narrow

## Immediate Diagnostics To Add

Before replacing infrastructure, add timing and size logs around each stage. Without this, it is easy to optimize the wrong layer.

### Backend Metrics

Add logs in `get_timeseries_result()` for:

- Redis get time
- cache hit/miss
- cached payload byte size
- JSON decode time
- bounds query time
- Databricks query time
- returned row count
- JSON encode time
- Redis set time
- final payload byte size
- bucket seconds
- requested signals count

### Databricks Metrics

Log:

- SQL text hash
- query duration
- row count
- selected bucket size
- selected filters
- whether bounds were inferred or provided

### Frontend Metrics

Log or measure:

- HTTP request duration
- response byte size
- `response.json()` time
- pandas DataFrame construction time
- `to_dict("records")` time
- main figure build time
- normalized figure build time
- browser render time

### Browser Metrics

Use DevTools to inspect:

- waiting time
- content download time
- response size compressed/uncompressed
- JavaScript parse/render time
- Plotly render duration

## Tactical Improvements

### 1. Enable HTTP Compression

Add FastAPI compression for large JSON responses:

```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1024)
```

Expected benefit:

- lower network transfer size
- faster response delivery for large JSON payloads

Tradeoff:

- extra CPU for compression
- does not reduce backend query time or frontend rendering time

### 2. Separate Redis Databases

Use separate Redis DBs or instances:

```text
Redis DB 0: frontend sessions
Redis DB 1: backend query cache
```

Expected benefit:

- cleaner memory management
- less eviction interference
- easier troubleshooting

### 3. Use Faster Serialization

Replace stdlib `json` with `orjson` for backend cache serialization and possibly FastAPI response serialization.

Potential changes:

- store compressed bytes instead of decoded strings
- disable `decode_responses=True` for the query cache Redis pool
- use `orjson.dumps()` / `orjson.loads()`
- optionally compress with zstd/gzip for large cached payloads

Expected benefit:

- lower CPU cost on cache hit/miss
- smaller Redis payloads if compressed

Tradeoff:

- more implementation complexity
- still not a replacement for better serving tables

### 4. Avoid Large `dcc.Store` Payloads

Instead of storing all timeseries records in Dash state, store a server-side cache key and keep the data server-side.

Current pattern:

```text
Dash Store contains all records
```

Better pattern:

```text
Dash Store contains request_id/cache_key
server-side cache contains rows or figure payload
```

Expected benefit:

- less Dash JSON serialization
- less browser memory pressure
- fewer repeated DataFrame conversions

### 5. Build Both Figures In One Callback Or Cache Figure Inputs

The current page builds the main and normalized figures in separate callbacks from the same records. Consider:

- one callback that builds both figures together
- memoizing parsed DataFrame construction
- storing precomputed figure-ready arrays instead of raw records

Expected benefit:

- fewer repeated pandas conversions
- lower frontend CPU time

### 6. Enforce Adaptive Resolution At The API Boundary

The API should prevent accidental large payloads. It should choose grain based on time range and max points.

Example:

```text
0-2 hours   -> 1s or 5s
2-24 hours  -> 10s or 1m
1-7 days    -> 1m or 5m
7-30 days   -> 5m or 15m
30+ days    -> 1h
```

The frontend should request intent, not raw resolution:

```text
from_ts, to_ts, signals, max_points
```

The backend should choose the source table and grain.

## Strategic Architecture Improvements

### Option A: Databricks SQL With Pre-Aggregated Serving Tables

This is the simplest Databricks-native strategy.

Keep Databricks Delta as the source of truth, but create app-facing serving tables:

```text
holmes_timeseries_1m
holmes_timeseries_5m
holmes_timeseries_15m
holmes_timeseries_1h
holmes_experiment_summary
holmes_signal_catalog
```

Recommended schema:

```text
order_id
sample_name
testrig_id
signal_id
bucket_start
value_min
value_max
value_avg
value_last
sample_count
```

Benefits:

- avoids request-time aggregation over the large source view
- stays governed in Databricks
- lower operational complexity
- good first architecture improvement

Limitations:

- Databricks SQL warehouse still has startup/concurrency/cost characteristics
- may not feel sub-second for highly interactive apps

### Option B: Lakebase Postgres As An App-Serving Database

Lakebase Postgres can be a good serving layer if the data engineer owns the schema and publishes app-ready aggregates.

Recommended use:

```text
Databricks Delta = full source of truth
Databricks jobs = aggregate and publish serving data
Lakebase Postgres = indexed app-serving database
Application = simple indexed SELECT queries
```

Good Lakebase tables:

```text
experiment_summary
signal_catalog
timeseries_1m
timeseries_5m
timeseries_1h
event_overlay
dashboard_default_view
```

Recommended indexes:

```sql
CREATE INDEX ON timeseries_5m (order_id, signal_id, bucket_start);
CREATE INDEX ON timeseries_5m (testrig_id, signal_id, bucket_start);
CREATE INDEX ON timeseries_5m (sample_name, signal_id, bucket_start);
CREATE INDEX ON timeseries_5m (order_id, testrig_id, sample_name, signal_id, bucket_start);
```

Benefits:

- lower request latency than Databricks for indexed serving queries
- app developer only writes simple SQL
- data engineer controls physical model
- good fit for curated, reduced, app-shaped data

Limitations:

- not ideal for raw 500M-row analytical scans
- row-store engine; large aggregations can be slower than columnar engines
- requires data publishing and index maintenance

Important constraint:

Do not dump the full raw 500M-row table into Postgres as the main app table. Publish reduced, indexed, pre-aggregated tables.

### Option C: ClickHouse As The Timeseries Serving Engine

ClickHouse is often a stronger choice than Postgres for very large analytical timeseries visualization.

Recommended use:

```text
Databricks Delta = source of truth
Databricks pipeline = publishes curated serving data
ClickHouse = high-performance chart serving
Lakebase/Postgres = app metadata and dashboard configuration
Redis = small hot cache only
```

Benefits:

- columnar storage
- excellent compression
- very fast time-range aggregations
- high concurrency for dashboard workloads
- strong fit for large analytical timeseries slices

Limitations:

- additional system to operate
- governance and data movement need design
- less Databricks-native than Lakebase

### Option D: Time-Series Database

A classic time-series database can help if queries are mostly:

```text
measurement + tags + time range -> time series
```

Examples:

- TimescaleDB
- InfluxDB
- QuestDB

Benefits:

- natural time-window model
- retention and downsampling features
- useful for sensor-style workloads

Limitations:

- may be less flexible for wide analytical dashboard slicing
- not always better than ClickHouse for high-volume analytical queries
- schema/tag design must be careful

For HOLMES, ClickHouse or Databricks serving tables may be a better fit than a classic metrics-oriented TSDB.

### Option E: SQL Flight / Arrow Flight SQL

Arrow Flight SQL can reduce transport and serialization overhead by moving columnar binary data instead of JSON.

Benefits:

- faster transfer than JSON for large result sets
- lower Python conversion overhead
- good for service-to-service analytics transport

Limitations:

- not a database strategy by itself
- does not fix too many points, request-time aggregation, or browser rendering
- frontend still needs chart-sized data

Use Flight only after reducing payload size and building better serving tables.

## Recommended Target Architecture

The strongest practical design is:

```text
Databricks Delta
  full source of truth, full-resolution history, governed transformations

Databricks jobs
  build multi-resolution serving aggregates

Lakebase Postgres or ClickHouse
  low-latency app-serving tables

Redis
  small metadata cache, auth/session cache, short-lived small responses

FastAPI backend
  validates filters, chooses grain, queries serving database, returns chart-sized payloads

Dash frontend
  renders already-downsampled data, avoids storing huge raw records in dcc.Store
```

## Recommended Implementation Roadmap

### Phase 1: Measure And Reduce Waste

1. Add stage-level backend timings and payload-size logs.
2. Add frontend timings around request, JSON parsing, DataFrame creation, and figure build.
3. Enable HTTP gzip compression.
4. Separate Redis DBs for sessions and backend cache.
5. Add cache hit/miss and payload-size metrics.
6. Enforce strict `max_points` and adaptive grain selection.

### Phase 2: Improve Current Backend

1. Use `orjson` for cache serialization.
2. Store compressed bytes in Redis for large payloads.
3. Avoid storing large records directly in `dcc.Store`.
4. Cache figure-ready data or server-side request keys instead of raw records.
5. Combine duplicate dashboard requests where possible.

### Phase 3: Build Serving Tables

1. Create Databricks aggregate tables at 1m, 5m, 15m, and 1h grains.
2. Route API requests to the correct grain based on time range and `max_points`.
3. Keep raw/high-resolution queries only for narrow drill-down windows.
4. Optimize Databricks tables with clustering around common filters.

### Phase 4: Add Dedicated Serving Database If Needed

If Databricks serving tables are still too slow or too expensive under concurrency:

1. Publish curated aggregate tables to Lakebase Postgres or ClickHouse.
2. Use Lakebase Postgres if operational simplicity and Databricks-native managed Postgres are more important.
3. Use ClickHouse if high-concurrency, low-latency analytical chart serving is the priority.
4. Keep Redis for small hot cache entries only.

## Final Recommendation

The current app is slow because the request path moves too much chart data through too many expensive conversion layers. Redis only skips the Databricks query on cache hits; it does not eliminate JSON parsing, FastAPI serialization, frontend pandas conversion, Dash state transfer, Plotly figure construction, or browser rendering.

The best near-term fix is:

1. instrument the pipeline end-to-end,
2. enable compression,
3. reduce payload sizes with adaptive grain,
4. stop using Redis as a large JSON blob cache,
5. avoid large `dcc.Store` payloads.

The best strategic fix is:

1. pre-aggregate timeseries into app-serving grains,
2. serve those aggregates from Databricks SQL, Lakebase Postgres, or ClickHouse,
3. reserve raw 1-second data for narrow drill-down queries only.

Lakebase Postgres can be faster if it serves curated, indexed, pre-aggregated tables. It should not be used as a raw replacement for the full 500M-row analytical timeseries table.
