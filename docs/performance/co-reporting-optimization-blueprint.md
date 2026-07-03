# CO Reporting Optimization Blueprint

## Purpose

This document turns the current migration analysis into an implementation plan for a performant Sherlock-only CO reporting application.

It focuses on three questions:

1. What is structurally correct in the Databricks pipeline today?
2. Why does the old Dash interaction model remain expensive even after moving to Databricks and Redis?
3. What serving and UI architecture should replace the legacy callback-heavy model?

## Executive Summary

The Databricks pipeline data model is fundamentally sound for scale.

The current application performance problem is not primarily the Gold fact model. The bigger problem is that the frontend still follows the original Dash pattern: many server callbacks, server-side pandas DataFrames, repeated figure rebuilds, and repeated client-server round-trips for normal interactive behavior.

The current migration is a good compatibility bridge, but not yet the final optimized architecture.

The target architecture should be:

- Databricks Gold remains the durable analytical source of truth.
- Additional serving-oriented Gold tables or views are added for app access patterns.
- The backend serves narrow windowed slices, not full experiment payloads by default.
- The browser owns most view-state changes locally.
- Python callbacks are reserved for semantic query changes, not routine zoom and UI synchronization.

## What The Current Dash App Does

The migrated CO reporting app is still structurally close to the original Dash app.

Relevant files:

- `frontend/spaces/sherlock/co_energystacck_migration/reporting_dashboard.py`
- `frontend/spaces/sherlock/co_energystacck_migration/tabs/standard_reports.py`
- `frontend/spaces/sherlock/co_energystacck_migration/tabs/custom_reports.py`
- `frontend/spaces/sherlock/co_energystacck_migration/tabs/tab_helpers.py`
- `frontend/spaces/sherlock/co_energystacck_migration/holmes_data_provider.py`

### Observed interaction model

Standard Reports currently behaves like this:

1. User selects a series.
2. Dash callback loads raw and aggregate data into server memory.
3. A second callback builds a Plotly figure in Python.
4. A zoom or relayout event triggers another callback.
5. Python decides whether to switch resolution.
6. Python rebuilds the figure and sends it back to the browser.

Custom Reports follows the same basic model, but with more state dimensions:

- multi-series selection
- tag filters
- facet settings
- legend settings
- X and Y control synchronization
- time filter and non-time filter behavior
- resolution selection and fallback

The result is correct behavior, but the interaction loop is still server-centric.

### Why this is expensive

This model creates avoidable cost in four places:

1. Callback orchestration overhead inside Dash.
2. Python DataFrame reshaping and figure reconstruction.
3. Figure JSON serialization and network transfer.
4. Repeated browser redraws after backend responses.

This is particularly inefficient for the kinds of interactions users perform constantly in plotting apps:

- zoom
- pan
- reset view
- axis range adjustments
- changing plot overlays
- switching among already-loaded resolutions

Those interactions should mostly be local to the browser unless they materially change the requested data slice.

## What The Databricks Pipeline Gets Right

Relevant files:

- `CO2ELY_ENERGYSTACK/CO2ELY_ENERGYSTACK/bosch_co2ely_adb_batch/src/_3_s2g/gold_timeseries_view.py`
- `CO2ELY_ENERGYSTACK/CO2ELY_ENERGYSTACK/bosch_co2ely_adb_batch/src/_3_s2g/gold_summary_statistics.py`
- `CO2ELY_ENERGYSTACK/CO2ELY_ENERGYSTACK/bosch_co2ely_adb_batch/src/_5_common/common_config.py`

### Gold fact model is appropriate

`gold_timeseries` is a long-format raw fact table with grain:

- `series`
- `uuid`
- `group`
- `sample_offset`
- `channel`

with promoted columns:

- `timestamp`
- `elapsed_time_s`
- `channel_name`
- `unit`
- `value`
- `value_str`

This is a good durable analytical shape because it:

- preserves source-level flexibility
- scales to many channels
- supports derived signals naturally
- avoids needing a wide sparse schema in storage

### 1-minute aggregate table is correct and necessary

`gold_timeseries_agg` is also the right direction.

Its grain is:

- `series`
- `uuid`
- `group`
- `elapsed_bin_s`
- `channel`

with:

- `value_mean`
- `value_min`
- `value_max`
- `value_count`
- representative `timestamp`
- representative `elapsed_time_s`

This is already suitable for:

- experiment discovery
- channel discovery
- medium-resolution plotting
- summary-style charting

### Incremental append-only behavior is good

The append-only pair-based processing in `gold_timeseries_view.py` is aligned with the app’s operational needs.

Benefits:

- new experiments append cheaply
- existing experiments are not recomputed unnecessarily
- backfill of missing aggregates is possible
- table semantics are simple and predictable

### Schema/catalog resolution is clean

The environment-aware config in `common_config.py` is also correct:

- catalog: `ps_xplatform_{env}`
- schema: `co2elyd_{env}`

This is a strong foundation for a Holmes-integrated serving layer.

## Where The Current Serving Path Is Still Weak

Relevant files:

- `backend/services/co_reporting.py`
- `frontend/spaces/sherlock/co_energystacck_migration/holmes_data_provider.py`

### Good decisions already in place

The migrated backend already improves on the old model in some important ways:

- experiment discovery reads from `gold_timeseries_agg`
- channel discovery reads from `gold_timeseries_agg`
- Redis caches query results
- backend routes are scoped to the Sherlock CO reporting use case

Those decisions should remain.

### Remaining serving problems

The current path still retains too much legacy behavior:

1. The backend returns long rows to Python.
2. The frontend provider pivots those rows into wide pandas DataFrames.
3. Full series payloads are loaded eagerly per selected experiment.
4. Dash server memory becomes a session-level working store.
5. Interaction logic is built around those cached in-process DataFrames.

This means the app is still optimized around compatibility with the old tabs, not around efficient serving.

## Main Optimization Principle

The browser should own visual state.

The backend should own semantic data selection.

Databricks should own aggregation and serving-friendly precomputation.

If an interaction does not materially change the requested data, it should not require a backend round-trip.

If an interaction does materially change the data, the backend should fetch only the minimum required slice.

## Recommended Target Architecture

## 1. Add a serving layer on top of current Gold

Keep the existing Gold fact tables.

Add serving-oriented tables or views for application hot paths.

### Recommended additions

#### A. Experiment index table

Grain:

- one row per `series, uuid, group`

Suggested columns:

- `series`
- `uuid`
- `group`
- `start_time`
- `end_time`
- `duration_s`
- `sample_count`
- `channel_count`
- key derived KPI fields
- optional experiment classification fields

Purpose:

- populate series dropdowns
- avoid repeated aggregate scans for experiment lists
- support quick summaries and metadata panels

#### B. Channel catalog table

Grain:

- one row per `series, uuid, group, channel`

Suggested columns:

- `series`
- `uuid`
- `group`
- `channel`
- `channel_name`
- `unit`
- optional category or signal family
- optional availability flags for standard reports

Purpose:

- populate channel selectors cheaply
- avoid repeated `GROUP BY channel` on fact tables
- support report-specific signal discovery

#### C. Multi-resolution plot-serving tables

The current pipeline publishes raw and 1-minute aggregates.

The app conceptually wants at least three tiers:

- fine: raw
- medium: 1-minute
- coarse: 15-minute or similar

Add one or more additional aggregate tables, for example:

- `gold_timeseries_agg_1m`
- `gold_timeseries_agg_15m`
- optionally `gold_timeseries_agg_1h`

This can be implemented either as separate tables or a single table with an `agg_level` column.

Purpose:

- prevent expensive coarse plotting from falling back to the wrong grain
- simplify resolution switching logic
- cap returned point counts predictably

#### D. Standard-report serving views

Standard Reports are fixed templates.

For those, create serving views that already expose the required signal families and naming conventions expected by the chart definitions.

Purpose:

- reduce per-request reshaping in Python
- make Standard Reports cheaper than Custom Reports
- allow report-specific optimizations without constraining exploratory analysis

## 2. Change the backend API contract

The backend should stop assuming that the frontend wants the full selected experiment loaded into memory.

### Current contract

Current effective contract is close to:

- list all experiments
- list all channels for an experiment
- fetch all raw or all aggregate rows for chosen channels

### Recommended contract

Use explicit windowed, resolution-aware queries.

Suggested read API shape:

- `GET /series`
- `GET /series/{id}/channels`
- `POST /timeseries/query`

Suggested query body:

```json
{
  "series": "PoC Stack VI",
  "uuid": "...",
  "group": "...",
  "channels": ["Stack Voltage", "Current density"],
  "resolution": "auto",
  "visible_start_s": 0,
  "visible_end_s": 21600,
  "prefetch_margin_s": 3600,
  "mode": "standard_report"
}
```

Behavior:

- backend chooses the best serving table
- backend returns only the requested interval plus small context margin
- backend returns plot-ready rows for that interval
- backend may include metadata like chosen resolution and point count

### Why this is better

Benefits:

- no need to hold full series in Dash worker memory
- lower network transfer
- fewer pandas transformations
- better concurrency characteristics
- cleaner Redis key space

## 3. Move most interaction state client-side

### Should remain local in the browser

These actions should not need Python callbacks unless they cross a query boundary:

- zooming inside already-loaded data
- panning inside already-loaded data
- axis range edits
- toggling visible traces
- legend interactions
- switching between already-fetched representations

### Should trigger backend fetches

These actions should trigger a backend query:

- selecting a different experiment
- changing the channel set materially
- changing time window outside current buffered slice
- switching to a different resolution tier
- changing to a report definition that requires new signals

### Practical Dash implication

Dash should use fewer Python callbacks and more clientside callbacks for:

- input synchronization
- local figure updates
- visible window tracking
- lightweight UI state transitions

The backend should be invoked only for query-worthy state changes.

## 4. Separate Standard Reports and Custom Reports operationally

These two modes should not be optimized the same way.

### Standard Reports

Characteristics:

- fixed chart templates
- predictable signal sets
- predictable aggregations
- repeated access patterns

Optimization approach:

- precompute report-serving shapes where useful
- use aggressive Redis caching
- keep query keys stable
- return plot-ready payloads

### Custom Reports

Characteristics:

- exploratory
- variable channel combinations
- variable X/Y dimensions
- potentially multi-series comparison

Optimization approach:

- constrain request payloads to the visible window
- cap returned point counts
- require explicit resolution tiering
- use browser-owned state for most visual adjustments
- treat raw mode as drill-down, not the default initial load

## 5. Reduce in-process pandas as the working state model

The current compatibility layer uses pandas DataFrames as the in-memory session working set.

That was useful to preserve tab behavior quickly, but it should not be the long-term architecture.

### Better long-term options

Ordered from least disruptive to most disruptive:

1. Keep pandas but only for the currently visible slice.
2. Return lighter plot-ready JSON payloads and build traces directly.
3. Introduce client-side resampling or trace decimation where appropriate.
4. Use a more purpose-built visualization delivery pattern for very large traces.

### What not to do long term

Avoid keeping all of these in memory per session by default:

- full raw experiment payloads
- full aggregate payloads
- full channel catalogs decorated onto frames
- duplicate standard/custom caches for the same experiment

## 6. Improve the Redis strategy

Redis should support a good serving contract, not hide a poor one.

### Cache what matters

Good cache dimensions:

- experiment identity
- serving resolution tier
- channel set fingerprint
- time window bucket or tile
- report definition version

### Avoid unstable cache fragmentation

If every tiny zoom delta changes the cache key, hit rate will stay poor.

Use window tiling or quantized query windows where practical.

Example:

- cache 1-hour tiles for raw
- cache 6-hour or 24-hour tiles for 1-minute
- cache broader tiles for 15-minute

Then serve the viewport by stitching cached tiles.

## 7. Add missing app-facing summary surfaces in the pipeline

`gold_summary_statistics.py` is directionally useful, but the app needs summary data at experiment grain, not just broad table-level aggregates.

Recommended summary outputs:

- per `series, uuid, group` summary KPIs
- per report family summary KPIs
- optional phase or segment summaries if the domain supports them

Purpose:

- summary cards without touching timeseries facts
- report preselection hints
- faster overview pages
- easier filtering and ranking

## Concrete recommendations by layer

## Pipeline

Recommended next changes:

1. Keep `gold_timeseries` unchanged as the raw durable fact.
2. Keep `gold_timeseries_agg` as the 1-minute serving layer.
3. Add a coarser aggregate layer for large-window visualization.
4. Add experiment index and channel catalog serving tables.
5. Add per-experiment summary statistics instead of only broad table-level stats.
6. Optionally add Standard Report-specific serving views.

## Backend

Recommended next changes:

1. Add explicit windowed query parameters to CO reporting endpoints.
2. Make resolution selection backend-owned, with an `auto` option.
3. Return chosen resolution and point count in responses.
4. Cache windowed slices or tiles, not just full experiment result sets.
5. Avoid extra Python reshaping where a SQL-serving view can do the job.

## Frontend

Recommended next changes:

1. Keep Dash Pages and Sherlock integration as-is.
2. Reduce Python callback count in the reporting tabs.
3. Move control synchronization and view-state tracking client-side.
4. Replace eager full-series loading with buffered window loading.
5. Treat raw resolution as drill-down only.
6. Keep Standard and Custom report fetch paths separate where useful.

## Migration sequence

A practical low-risk sequence is:

### Phase 1: Improve serving without breaking UI

- keep current tab layouts
- add windowed backend query parameters
- stop loading full series by default
- keep Redis, but cache windowed slices
- move simple UI sync to clientside callbacks

### Phase 2: Add missing Gold serving assets

- add 15-minute aggregate layer
- add experiment index table
- add channel catalog table
- add per-experiment summary statistics

### Phase 3: Simplify the frontend working model

- reduce pandas-heavy state
- reduce server callbacks further
- make most zoom and visual interactions browser-local
- use backend only for data-boundary changes

## What Should Stay From The Current Migration

The following decisions were correct and should remain:

- Sherlock-only integration approach
- dedicated CO reporting backend routes
- use of Gold tables instead of local CSV or silver file emulation
- use of `gold_timeseries_agg` for experiment and channel discovery
- Redis caching in front of Databricks SQL
- compatibility-first migration through a provider facade

## What Should Change Next

The following is still legacy behavior and should be phased out:

- eager full-series loading into Dash worker memory
- server-side callback handling for ordinary zoom and relayout behavior
- server-side figure rebuilds for interactions that do not require new data
- broad pandas reshaping as the main serving strategy
- treating Standard and Custom reports as if they need the same delivery model

## Final Recommendation

Do not spend the next optimization cycle micro-tuning callback code in isolation.

The real leverage is architectural:

- make Databricks provide better serving grains
- make the backend serve narrow, resolution-aware windows
- make the browser keep view state locally
- reserve Python callbacks for semantic query changes only

That is the path that aligns the app with the strengths of the Gold pipeline and removes the biggest inefficiency inherited from the old Holmes Dash model.
