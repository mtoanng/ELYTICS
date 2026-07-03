# CO Reporting Serving API Design

## Purpose

This document defines the next backend and pipeline step for the Sherlock CO reporting migration.

It is intentionally more concrete than the optimization blueprint. The goal is to give implementation-ready guidance for:

- the backend API contract
- the serving tables or views the Databricks pipeline should expose
- Redis caching behavior
- the expected frontend query model

Relevant current code:

- `backend/routers/co_reporting.py`
- `backend/services/co_reporting.py`
- `frontend/spaces/sherlock/co_energystacck_migration/holmes_data_provider.py`
- `frontend/spaces/sherlock/co_energystacck_migration/tabs/standard_reports.py`
- `frontend/spaces/sherlock/co_energystacck_migration/tabs/custom_reports.py`

## Current Contract

The current CO reporting backend exposes three endpoints:

- `GET /api/sherlock/co-reporting/series`
- `GET /api/sherlock/co-reporting/channels`
- `GET /api/sherlock/co-reporting/timeseries`

Current `timeseries` contract:

- identifies one experiment by `series`, `uuid`, and `group`
- accepts a list of channels
- accepts `resolution=raw|agg`
- returns the full selected series for those channels at the requested grain

This is a good migration bridge, but not the right long-term serving contract.

## Target Contract

The target contract should be windowed, resolution-aware, and explicit about response metadata.

## Endpoint Set

Recommended endpoint set:

- `GET /api/sherlock/co-reporting/series`
- `GET /api/sherlock/co-reporting/channels`
- `POST /api/sherlock/co-reporting/query`
- optionally `GET /api/sherlock/co-reporting/summary`

## 1. Series endpoint

### Endpoint

`GET /api/sherlock/co-reporting/series`

### Purpose

Return experiment-level metadata for selectors, summaries, and initial page load.

### Request parameters

Optional:

- `series_family`
- `limit`
- `offset`
- `sort_by`
- `sort_order`
- optional future metadata filters

### Response shape

```json
{
  "data": [
    {
      "series": "PoC Stack VI",
      "uuid": "...",
      "group": "Conditioning",
      "start_time": "2026-02-14T10:01:27Z",
      "end_time": "2026-02-15T05:11:09Z",
      "duration_s": 68982,
      "sample_count": 481223,
      "channel_count": 93,
      "kpis": {
        "avg_stack_voltage_v": 14.2,
        "avg_fe_co_pct": 92.1
      }
    }
  ],
  "meta": {
    "returned": 1,
    "source": "gold_experiment_index"
  }
}
```

### Serving source

Recommended source:

- `gold_experiment_index`

Not recommended for long term:

- direct `GROUP BY` scans over `gold_timeseries_agg`

## 2. Channel endpoint

### Endpoint

`GET /api/sherlock/co-reporting/channels`

### Required parameters

- `series`
- `uuid`
- `group`

### Purpose

Return the available channels for an experiment, plus optional channel metadata used by Standard and Custom Reports.

### Response shape

```json
{
  "data": [
    {
      "channel": "stack_voltage",
      "channel_name": "Stack Voltage",
      "unit": "V",
      "signal_family": "electrical",
      "standard_report_roles": ["power", "efficiency"]
    }
  ],
  "meta": {
    "returned": 1,
    "source": "gold_channel_catalog"
  }
}
```

### Serving source

Recommended source:

- `gold_channel_catalog`

## 3. Query endpoint

### Endpoint

`POST /api/sherlock/co-reporting/query`

Use POST instead of GET because the request object can become large and semantically represents a query spec.

### Purpose

Return only the plot window needed by the current view.

### Request shape

```json
{
  "series": "PoC Stack VI",
  "uuid": "...",
  "group": "Conditioning",
  "channels": ["Stack Voltage", "Current density"],
  "visible_start_s": 0,
  "visible_end_s": 21600,
  "prefetch_margin_s": 1800,
  "resolution": "auto",
  "mode": "standard_report",
  "report_id": "stack_efficiency_main",
  "include_band": true
}
```

### Required fields

- `series`
- `uuid`
- `group`
- `channels`
- `visible_start_s`
- `visible_end_s`

### Optional fields

- `prefetch_margin_s`
- `resolution`
- `mode`
- `report_id`
- `include_band`
- optional future `downsample_policy`
- optional future `legend_grouping`

### Resolution behavior

Allowed values:

- `auto`
- `raw`
- `agg_1m`
- `agg_15m`
- optional future `agg_1h`

When `resolution=auto`, the backend chooses based on the effective request span.

### Effective query window

The backend should compute:

- `query_start_s = visible_start_s - prefetch_margin_s`
- `query_end_s = visible_end_s + prefetch_margin_s`

clamped to experiment bounds.

This gives the frontend enough buffer for immediate panning and modest zoom expansion without a second round-trip.

### Response shape

```json
{
  "data": [
    {
      "elapsed_time_s": 0,
      "timestamp": "2026-02-14T10:01:27Z",
      "channel": "stack_voltage",
      "channel_name": "Stack Voltage",
      "unit": "V",
      "value_mean": 14.21,
      "value_min": 14.18,
      "value_max": 14.24,
      "value_count": 60
    }
  ],
  "meta": {
    "series": "PoC Stack VI",
    "uuid": "...",
    "group": "Conditioning",
    "requested_resolution": "auto",
    "served_resolution": "agg_1m",
    "visible_start_s": 0,
    "visible_end_s": 21600,
    "query_start_s": 0,
    "query_end_s": 23400,
    "returned_points": 721,
    "channels_returned": 2,
    "source": "gold_timeseries_agg_1m",
    "cache": {
      "hit": true,
      "key": "co_reporting_query:..."
    }
  }
}
```

### Important design rule

The backend should return long-format plot-serving rows.

The frontend may still pivot for backward compatibility during the migration, but the backend contract should remain long and metadata-rich.

This keeps the API stable while allowing the frontend implementation to evolve.

## 4. Summary endpoint

### Endpoint

`GET /api/sherlock/co-reporting/summary`

### Required parameters

- `series`
- `uuid`
- `group`

### Purpose

Return fast summary KPI cards without touching the raw or aggregate timeseries facts.

### Response shape

```json
{
  "data": {
    "avg_stack_voltage_v": 14.2,
    "peak_current_density_ma_cm2": 502.1,
    "avg_fe_co_pct": 92.1,
    "avg_spce_pct": 44.8
  },
  "meta": {
    "source": "gold_experiment_summary"
  }
}
```

## Serving Tables Or Views

The current pipeline already produces:

- `gold_timeseries`
- `gold_timeseries_agg`

That should remain.

The app should add the following serving assets.

## 1. `gold_experiment_index`

### Grain

One row per `series, uuid, group`

### Purpose

Used by:

- experiment selector
- start/end range display
- quick metadata panels
- summary cards list view

### Suggested columns

- `series`
- `uuid`
- `group`
- `start_time`
- `end_time`
- `duration_s`
- `sample_count`
- `channel_count`
- optional `series_family`
- optional `stack_generation`
- optional summary KPIs

### Build source

Derived from:

- `gold_timeseries_agg`
- optional join to summary output

## 2. `gold_channel_catalog`

### Grain

One row per `series, uuid, group, channel`

### Purpose

Used by:

- channel dropdowns
- report signal resolution
- tag or category enrichment

### Suggested columns

- `series`
- `uuid`
- `group`
- `channel`
- `channel_name`
- `unit`
- optional `signal_family`
- optional `report_roles`
- optional `display_order`

### Build source

Derived from:

- `gold_timeseries_agg`
- optional mapping metadata from config

## 3. `gold_timeseries_agg_15m`

### Grain

One row per `series, uuid, group, elapsed_bin_15m_s, channel`

### Purpose

Used by:

- wide window plotting
- zoomed-out comparison charts
- Standard Report initial loads

### Suggested columns

- `series`
- `uuid`
- `group`
- `elapsed_bin_s`
- `timestamp`
- `elapsed_time_s`
- `channel`
- `channel_name`
- `unit`
- `value_mean`
- `value_min`
- `value_max`
- `value_count`

### Build source

Preferred source:

- aggregate from `gold_timeseries`
- or aggregate from `gold_timeseries_agg` if fidelity is acceptable

## 4. `gold_experiment_summary`

### Grain

One row per `series, uuid, group`

### Purpose

Used by:

- KPI cards
- selector enrichment
- overview panels
- fast metadata responses

### Suggested columns

- `series`
- `uuid`
- `group`
- `avg_stack_voltage_v`
- `peak_current_density_ma_cm2`
- `avg_energy_efficiency_pct`
- `avg_fe_co_pct`
- `avg_fe_h2_pct`
- `avg_spce_pct`
- `start_time_s`
- `end_time_s`

### Important note

The current `gold_summary_statistics.py` should evolve toward experiment-grain output rather than only a broad aggregate result.

## Backend Resolution Policy

The backend should own `auto` resolution decisions.

Suggested thresholds:

- `span <= 2h` -> `raw`
- `2h < span <= 72h` -> `agg_1m`
- `span > 72h` -> `agg_15m`

These thresholds are not final constants. They should be tuned against actual point counts and browser rendering performance.

The important architectural rule is that the backend, not the frontend, should own the serving-table choice.

## Redis Caching Strategy

## Cache key dimensions

Recommended key dimensions for query caching:

- `series`
- `uuid`
- `group`
- canonical sorted channel set fingerprint
- served resolution
- quantized `query_start_s`
- quantized `query_end_s`
- mode or report identifier where relevant

## Tile strategy

Use tiled windows where practical.

Examples:

- raw tiled by 15-minute or 1-hour chunks
- `agg_1m` tiled by 6-hour or 24-hour chunks
- `agg_15m` tiled by 1-day or multi-day chunks

The backend can stitch tiles before returning the response.

Benefits:

- better cache hit rate during panning
- fewer unique keys from tiny viewport movements
- stable Redis memory behavior

## What not to cache as the primary strategy

Do not rely mainly on caching the full selected experiment for all requested channels.

That keeps the old eager-loading behavior alive and scales poorly across users and experiments.

## Frontend Expectations

The frontend should evolve toward this model:

1. On page load, request series index.
2. When an experiment is selected, request channel catalog and summary.
3. For the first chart render, request only the visible window at `resolution=auto`.
4. Keep visual-only interactions local while still within the buffered window.
5. Request another window only when panning or zooming crosses the buffered bounds or changes the requested channel set.

## Standard Reports vs Custom Reports

## Standard Reports

Recommended behavior:

- fixed report definitions map to known signal sets
- backend can pre-resolve channel lists
- initial loads should prefer aggregate tables
- report-specific serving views are acceptable

Response should optimize for:

- fast first paint
- stable cache keys
- low callback count

## Custom Reports

Recommended behavior:

- user-selected channels remain flexible
- default first render should use aggregate data
- raw mode should be explicit drill-down
- backend should enforce point-count discipline

Response should optimize for:

- flexibility without full-series eager loading
- bounded memory usage
- bounded payload sizes

## Migration Plan

## Phase 1

Implement without breaking the current UI contract completely:

1. Add `POST /query` alongside the existing `GET /timeseries`.
2. Add window parameters and served-resolution metadata.
3. Keep current routes for compatibility while the frontend is migrated.
4. Add response metadata for cache and point counts.

## Phase 2

Extend the pipeline:

1. Add `gold_experiment_index`.
2. Add `gold_channel_catalog`.
3. Add `gold_timeseries_agg_15m`.
4. Add experiment-grain summary output.

## Phase 3

Refactor the frontend:

1. Stop loading full series into Dash worker memory.
2. Move zoom and view-state synchronization client-side.
3. Use the buffered window query model.
4. Remove or drastically reduce the server-side resolution switching callbacks.

## Implementation Priority

If only one backend change is made first, it should be this:

Add a windowed `POST /api/sherlock/co-reporting/query` endpoint and stop treating full-series payloads as the default serving unit.

That change gives the frontend and backend a path to reduce callback-driven server churn without requiring the full serving-layer buildout on day one.
