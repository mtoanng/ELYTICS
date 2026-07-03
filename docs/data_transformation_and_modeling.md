# CO2 Energystack Data Transformation and Modeling

This document is the implementation-facing contract for the Databricks demo pipeline. It is intended for backend and frontend engineers who need to understand what data exists, how it is transformed, and which tables the new application should query.

Current demo path:

```text
ADLS raw Excel files
  -> _0_convert: XLSX converter, channel mapping, derived formulas
  -> parquet_raw: filemeta/channel/timeseries/statistics Parquet files
  -> _1_r2b: Bronze Delta tables via Auto Loader
  -> _3_s2g: Gold serving tables direct from Bronze
  -> application API / Redis cache / frontend
```

Silver and DQ modules remain in the repository, but the demo E2E job intentionally skips them. Gold reads Bronze directly.

## Operating Principles

- Converter output must be deterministic for the same source file path.
- Source evidence is retained in Bronze as long-format channel data.
- Demo semantic alignment happens in the converter using repo-managed JSON mapping files.
- Derived metrics are implemented in a dedicated module, not inline in orchestration code.
- Gold tables are append-only and optimized for application reads.
- Repeated UI requests should be served from Redis or application cache after the first SQL Warehouse query.

## Stage 0: Source Files

Raw experiment files are stored in ADLS under the configured raw prefix:

```text
raw_data/<series folder>/<file>.xlsx
```

The series folder is important because it selects the static channel mapping. Configured demo series are:

- `PoC Stack II`
- `PoC Stack III`
- `PoC Stack IV`
- `PoC Stack VI`

Mapping resolution checks every component of the relative path. This supports normal paths such as `PoC Stack VI/file.xlsx` and integration-test paths such as `test/PoC Stack VI/file.xlsx`.

## Stage 1: Converter

Main files:

- `src/_0_convert/run_converter.py`
- `src/_0_convert/xlsx_converter.py`
- `src/_0_convert/channel_mapping.py`
- `src/_0_convert/derived_metrics.py`
- `src/_0_convert/converter_utils.py`

The converter is Spark-distributed. The driver discovers new files through Azure SDK and sends files to workers with `mapPartitions`. Each worker downloads Excel bytes, converts sheets with Polars/calamine, and writes Parquet table outputs back to ADLS.

Worker modules distributed with `sparkContext.addPyFile`:

- `converter_utils.py`
- `channel_mapping.py`
- `derived_metrics.py`
- `xlsx_converter.py`

### Converter Sequence Per Sheet

1. Read the sheet with `pl.read_excel(..., engine="calamine", has_header=False)`.
2. Interpret row 1 as `channel` identifiers.
3. Interpret row 2 as display `channel_name` values.
4. Detect row 3 as `unit` only when the row looks like units.
5. Rename data columns to row 1 channel identifiers.
6. Merge split `Real time` date/time columns into a single `timestamp` channel.
7. Apply static channel mapping from file display names to canonical schema names.
8. Compute derived engineering metrics on the wide DataFrame.
9. Unpivot to long `timeseries` rows.
10. Emit `filemeta`, `channel`, `timeseries`, and `statistics` Parquet outputs.

### Timestamp Handling

Some Excel files use a merged `Real time` header over two columns. Calamine can expose this as:

- date column: `2026-02-14 00:00:00`
- time column: `1899-12-31 10:01:27`

The converter merges this into:

```text
2026-02-14 10:01:27
```

The resulting channel id is `timestamp`. It stays in Bronze as a normal timeseries row and is promoted to a proper timestamp column in Gold.

### Channel Mapping

Configuration files live under:

```text
sys_files/config_files/mappings/
```

Files:

- `series_config.json`: maps source series folder names to mapping files.
- `PoCII_mapping.json`
- `PoCIII_mapping.json`
- `PoCIV_mapping.json`
- `PoCVI_mapping.json`

Each mapping entry uses the original Dash app format:

```json
{
  "schema_column": "Current",
  "file_column": "Current",
  "example": "...",
  "origin": "..."
}
```

Mapping behavior:

- Matches `file_column` against Excel row 2 display names.
- Matching is trim and case insensitive.
- Empty `file_column` entries are skipped because they describe calculated fields.
- The output channel id and channel name are both changed to `schema_column`.
- Mapping runs before formulas so formula inputs use canonical names.

To add a new stack or experiment family:

1. Create a new mapping JSON file in `sys_files/config_files/mappings/`.
2. Add the source folder name and mapping file name to `series_config.json`.
3. Run the converter for a sample file and inspect `bronze_channel`.

### Derived Metrics

Derived formulas live in `src/_0_convert/derived_metrics.py`.

Constants:

| Constant | Value | Meaning |
| --- | ---: | --- |
| `ACTIVE_AREA_CM2` | 88.0 | active cell area for current density |
| `FARADAY_CONST` | 96485.3 | Faraday constant in C/mol |
| `VM_STP` | 22.414 | ideal gas molar volume at STP in L/mol |

Derived columns currently produced when inputs exist:

| Metric | Unit | Formula summary |
| --- | --- | --- |
| `Energy Efficiency` | `%` | `1.48 * FE_CO / (Stack Voltage / 5)` |
| `Δp Anolyte` | `bar` | `Anolyte inlet pressure - Anolyte outlet pressure` |
| `Current density` | `mA/cm²` | `1000 * Current / ACTIVE_AREA_CM2` |
| `Faradaic Efficiency of CO and H2` | `%` | `FE_CO + FE_H2` |
| `Flow CO out` | `nL/min` | `(FE_CO / 100 * Current / (2F)) * Vm * 60` |
| `Flow H2 out` | `nL/min` | `(FE_H2 / 100 * Current / (2F)) * Vm * 60` |
| `Flow O2 out` | `nL/min` | `(FE_O2 / 100 * Current / (4F)) * Vm * 60` |
| `Flow CO2 out, total` | `nL/min` | `Cathode inlet CO2 gas flow - Flow CO out` |
| `Flow CO2 out, anode` | `nL/min` | `(ratio * Flow O2 out) / (1 - ratio)` |
| `Flow CO2 out, cathode` | `nL/min` | `Flow CO2 out, total - Flow CO2 out, anode` |
| `CO/H2 ratio recalculated` | empty | `Flow CO out / Flow H2 out` |
| `Single Pass Conversion Efficiency` | `%` | `100 * CO formation rate / CO2 inflow rate` |

Formula behavior:

- Inputs are looked up by canonical channel names after mapping.
- Missing inputs skip only the affected metric.
- Outputs are appended as normal channels before unpivot.
- Infinite and NaN formula outputs are converted to null.
- Derived metrics appear in `bronze_channel`, `bronze_timeseries`, `gold_timeseries`, and `gold_timeseries_agg` exactly like raw channels.

## Stage 2: Raw Parquet Output

Converter outputs are written under the configured raw output prefix:

```text
parquet_raw/filemeta/
parquet_raw/channel/
parquet_raw/timeseries/
parquet_raw/statistics/
```

For integration tests, the suffix `_int_test` is added to the output prefix.

## Stage 3: Bronze Delta

Main file:

- `src/_1_r2b/ingest_parquet_to_bronze.py`

Bronze uses Auto Loader with `Trigger.AvailableNow`. It reads converter Parquet outputs and appends to Delta tables. Checkpoints are stored next to the raw Parquet output so repeated runs only ingest new files.

Bronze tables:

### `bronze_filemeta`

Grain: one row per source file.

| Column | Type | Meaning |
| --- | --- | --- |
| `uuid` | string | deterministic file id from relative path |
| `file_path` | string | full `abfss://` path when available |
| `raw_file_name` | string | source file name |
| `file_size` | long | source size in bytes |
| `last_modified` | timestamp | source blob modification time |
| `ingested_timestamp` | timestamp | converter runtime timestamp |
| `_bronze_ingested_at` | timestamp | Bronze ingestion time |

### `bronze_channel`

Grain: one row per file, sheet/group, and channel.

| Column | Type | Meaning |
| --- | --- | --- |
| `uuid` | string | file id |
| `group` | string | Excel sheet name |
| `channel` | string | channel id used by timeseries rows |
| `channel_name` | string | display/canonical channel name |
| `unit` | string | channel unit if detected or generated |
| `column_index` | int | channel order after timestamp merge/mapping/formulas |
| `_bronze_ingested_at` | timestamp | Bronze ingestion time |

### `bronze_timeseries`

Grain: one row per file, sheet/group, sample offset, and channel.

| Column | Type | Meaning |
| --- | --- | --- |
| `uuid` | string | file id |
| `group` | string | Excel sheet name |
| `sample_offset` | long | zero-based data-row offset inside the sheet |
| `channel` | string | channel id |
| `value` | double | numeric value when parseable |
| `value_str` | string | non-numeric string value when not parseable |
| `_bronze_ingested_at` | timestamp | Bronze ingestion time |

Important Bronze convention:

- `timestamp` is still a channel row in `bronze_timeseries`.
- elapsed/test time is still a channel row in `bronze_timeseries`.
- Gold promotes those structural rows into columns.

### `bronze_statistics`

Grain: one row per file and sheet/group.

| Column | Type | Meaning |
| --- | --- | --- |
| `uuid` | string | file id |
| `group` | string | Excel sheet name |
| `n_channels` | int | channels after timestamp merge, mapping, and formulas |
| `n_rows` | long | data rows in the sheet |
| `n_timeseries_rows` | long | `n_channels * n_rows` |
| `_bronze_ingested_at` | timestamp | Bronze ingestion time |

## Stage 4: Gold Serving Tables

Main file:

- `src/_3_s2g/gold_timeseries_view.py`

Gold reads directly from Bronze for the demo. It builds two append-only serving tables.

### `gold_timeseries`

Grain: one row per series, file, sheet/group, sample offset, and signal channel.

| Column | Type | Meaning |
| --- | --- | --- |
| `series` | string | parent folder extracted from `file_path` |
| `uuid` | string | file id |
| `group` | string | Excel sheet name |
| `sample_offset` | long | sample offset from Bronze |
| `timestamp` | timestamp | promoted from `channel = 'timestamp'` |
| `elapsed_time_s` | double | promoted from elapsed/test time channel |
| `channel` | string | signal channel id, excluding timestamp and elapsed time |
| `channel_name` | string | joined from `bronze_channel` |
| `unit` | string | joined from `bronze_channel` |
| `value` | double | numeric signal value |
| `value_str` | string | non-numeric signal value |

Natural key:

```text
series, uuid, group, sample_offset, channel
```

Gold excludes structural rows from signal rows:

- `channel = 'timestamp'`
- channels whose `channel` or `channel_name` matches elapsed/test time

### `gold_timeseries_agg`

Grain: one row per series, file, sheet/group, elapsed-time bin, and signal channel.

Default bin size: 60 seconds.

| Column | Type | Meaning |
| --- | --- | --- |
| `series` | string | parent folder extracted from `file_path` |
| `uuid` | string | file id |
| `group` | string | Excel sheet name |
| `elapsed_bin_s` | double | `floor(elapsed_time_s / 60) * 60` |
| `channel` | string | signal channel id |
| `channel_name` | string | signal display/canonical name |
| `unit` | string | unit |
| `elapsed_time_s` | double | first elapsed value in the bin |
| `timestamp` | timestamp | first timestamp in the bin |
| `value_mean` | double | average numeric value in the bin |
| `value_min` | double | minimum numeric value in the bin |
| `value_max` | double | maximum numeric value in the bin |
| `value_count` | long | count of numeric values in the bin |

Natural key:

```text
series, uuid, group, elapsed_bin_s, channel
```

Incremental behavior:

- `gold_timeseries` skips `(uuid, group)` pairs already written.
- `gold_timeseries_agg` is built from the new raw Gold rows.
- If raw Gold exists but aggregate rows are missing, the job backfills aggregate rows from existing `gold_timeseries` instead of reprocessing Bronze and duplicating raw rows.

## Job Flow

The demo E2E bundle flow is:

```text
tsk_converter -> tsk_bronze -> tsk_gold
```

Skipped for demo:

- `tsk_silver`
- `tsk_dq`
- `tsk_co2_gold_summary`, because it depends on Silver enriched outputs

## Application Consumption

Recommended backend pattern:

1. Query `gold_timeseries_agg` for chart views by default.
2. Query `gold_timeseries` for high-resolution drilldown or export.
3. Cache query results by `series`, `uuid`, `group`, selected channels, and resolution.
4. Use Redis TTL plus explicit invalidation after a successful pipeline run.
5. Keep SQL Warehouse queries off the hot UI path after cache warm-up.

Example cache keys:

```text
co2ely:series:{series}:groups
co2ely:timeseries_agg:{series}:{uuid}:{group}:{channel_hash}:60s
co2ely:timeseries_raw:{series}:{uuid}:{group}:{channel_hash}
```

Example backend filters:

```sql
SELECT *
FROM <catalog>.<schema>.gold_timeseries_agg
WHERE series = :series
  AND uuid = :uuid
  AND `group` = :group
  AND channel IN (:channels)
ORDER BY elapsed_bin_s, channel;
```

```sql
SELECT *
FROM <catalog>.<schema>.gold_timeseries
WHERE series = :series
  AND uuid = :uuid
  AND `group` = :group
  AND channel IN (:channels)
ORDER BY sample_offset, channel;
```

Frontend expectations:

- Use `timestamp` for wall-clock x-axis when present.
- Use `elapsed_time_s` or `elapsed_bin_s` for experiment-relative x-axis.
- Display `channel_name` and `unit` in legends/tooltips.
- Treat `value_str` as metadata/status-like signal values, not numeric chart values.
- Derived metrics are not special in Gold; they are channels selected like any other signal.

## Deferred Post-Demo Work

These are intentionally not required for the current demo but should be added before a full industrial release:

- Silver semantic layer for versioned mapping, formula, quality, and lineage outputs.
- DQ/plausibility rules ported from the original Dash enrichment path.
- Formula versioning and reproducibility metadata.
- Separate raw-vs-derived metric origin flag in the semantic layer.
- Backfill/recompute strategy for changed mappings and formulas.
- Multi-resolution aggregates beyond 60 seconds, for example 15 minutes.
- Summary/report tables equivalent to the original app's standard reports.
- Serving API contract and Redis invalidation protocol.

## Change Locations For Engineers

- Add or adjust a stack mapping: `sys_files/config_files/mappings/`.
- Add or adjust a derived formula: `src/_0_convert/derived_metrics.py`.
- Adjust Excel parsing and timestamp handling: `src/_0_convert/xlsx_converter.py`.
- Adjust Spark file distribution or converter orchestration: `src/_0_convert/run_converter.py`.
- Adjust Bronze ingestion: `src/_1_r2b/ingest_parquet_to_bronze.py`.
- Adjust Gold serving shape or aggregation: `src/_3_s2g/gold_timeseries_view.py`.
- Adjust demo job wiring: `resources/job_co2_e2e.yml` and `resources/job_co2_gold.yml`.
