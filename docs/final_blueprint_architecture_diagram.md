# Final Blueprint Architecture Diagram Spec

Use this as the source specification for an Excalidraw architecture diagram.

## Diagram Title

CO2 Energystack Final Migration Blueprint - Simplified Layered Architecture

## Layout

Use a left-to-right flow with six vertical lanes:

1. Source Files and Static Config
2. Converter / Raw Extraction
3. Bronze Raw Evidence
4. Silver Semantic Transform
5. Gold Serving Tables
6. Application Serving

## Lane 1: Source Files and Static Config

Box 1:
- Title: Raw Excel Files
- Notes:
  - uploaded source workbooks
  - multiple files per series
  - multiple sheets/logical groups per file
  - source values are the audit truth

Box 2:
- Title: Static Config
- Notes:
  - channel mapping
  - metric catalog
  - formula definitions
  - stack definitions
  - DQ and plausibility rules
  - versions stamped onto silver rows

Arrows:
- Raw Excel Files -> Converter / Raw Extraction
- Static Config -> Silver Semantic Transform

## Lane 2: Converter / Raw Extraction

Main box title:
- Converter / Raw Extraction

Inside list these steps:
1. parse Excel once with Polars/calamine
2. use worksheet/header configuration
3. preserve file, sheet/group, row, and channel lineage
4. emit raw channel metadata
5. emit raw timeseries values and raw strings
6. emit extraction statistics if already available

Add a side note:
- No semantic changes here
- no mapping
- no timestamp normalization
- no elapsed-time stitching
- no clipping
- no KPI calculation

Arrows:
- Converter / Raw Extraction -> Bronze Raw Evidence

## Lane 3: Bronze Raw Evidence

Main box title:
- Bronze Raw Evidence

Data model boxes:

Box 1:
- Title: bronze_filemeta
- Notes:
  - sheet/logical-group grain
  - uuid + group
  - file path and raw file name
  - file size and last modified
  - ingested timestamp
  - run id

Box 2:
- Title: bronze_channel
- Notes:
  - uuid + group + channel
  - raw channel name
  - raw unit
  - column index
  - run id

Box 3:
- Title: bronze_timeseries
- Notes:
  - uuid + group + sample_offset + channel
  - value
  - value_str
  - no dropped rows
  - no removed structural fields

Small optional note:
- bronze_statistics can remain operational metadata if converter already emits it

Add a rule banner:
- Bronze preserves. Silver interprets.

Arrows:
- Bronze Raw Evidence -> Silver Semantic Transform

## Lane 4: Silver Semantic Transform

Main box title:
- Silver Semantic Transform

Inside list:
- load static config
- apply static raw-channel-to-metric mapping
- normalize timestamp and elapsed time
- stitch elapsed time across sheets/files
- preserve raw strings and parse status
- use internal wide frame for formulas
- calculate derived metrics
- apply plausibility rules
- emit issue facts
- publish canonical long fact
- stamp mapping/formula/rule versions

Data model boxes:

Box 1:
- Title: silver_measurement_fact
- Notes:
  - uuid + group + sample_offset + metric_id + origin
  - event_timestamp
  - elapsed_time_s
  - value_double and value_raw_string
  - source and derived metrics
  - quality status
  - mapping/formula versions

Box 2:
- Title: silver_issue_fact
- Notes:
  - parse failures
  - mapping issues
  - continuity issues
  - formula issues
  - clipping actions

Side note:
- mapping/catalog/formulas are config, not day-one Delta tables
- keep elapsed_time_s on fact rows
- no required row_context table
- avoid long-table KPI self-joins

Arrows:
- Silver Semantic Transform -> Gold Serving Tables

## Lane 5: Gold Serving Tables

Main box title:
- Gold Serving Tables

Data model boxes:

Box 1:
- Title: gold_timeseries_raw
- Notes:
  - raw chart-serving values
  - selected from silver fact

Box 2:
- Title: gold_timeseries_1min
- Notes:
  - min / max / mean
  - 1-minute elapsed-time buckets

Box 3:
- Title: gold_timeseries_15min
- Notes:
  - min / max / mean
  - 15-minute elapsed-time buckets

Small optional note:
- metric summary and DQ status should be views only if the UI needs them

Add a small rule box:
- Resolution logic
- < 10h -> raw
- 10h to 100h -> 1min
- >= 100h -> 15min

Arrows:
- Gold Serving Tables -> API / Query Service

## Lane 6: Application Serving

Create three boxes.

Box 1:
- Title: API / Query Service
- Notes:
  - query gold only
  - narrow metric selection
  - bounded time windows
  - no local CSV or Feather reads

Box 2:
- Title: Standard Reports
- Notes:
  - Voltage
  - Gas Pressure
  - CO2 Flow
  - Anolyte Pressure
  - Faradaic Efficiency
  - Energy Efficiency
  - SPCE

Box 3:
- Title: Custom Reports and Exports
- Notes:
  - filtered queries
  - tags / facets
  - export payloads

Arrows:
- API / Query Service -> Standard Reports
- API / Query Service -> Custom Reports and Exports

## Bottom Banner

Add a bottom banner with the final rule:

Extract once -> preserve bronze -> interpret in silver -> aggregate in gold

Add a small footer:

Day-one model: 3 bronze tables, 2 silver tables, 3 gold tables.
