WITH base AS (
  SELECT
    ts.time,
    year(ts.time) AS year,
    ts.order_id,
    -- operational condition
    ts.iStck,
    -- order metadata
    o.testrig_id,
    o.sample_type,
    o.sample_state,
    o.number_of_cells,
    -- raw location
    tr.location AS raw_location
  FROM
    ps_xplatform_dev.pemely_ops.gold_genericstack_timeseries_1hr ts
      INNER JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_order o
        ON ts.order_id = o.order_id
      LEFT JOIN ps_xplatform_prod.pemely_dev.silver_dim_testrig tr
        ON o.testrig_id = tr.testrig_id
),
filtered AS (
  SELECT
    year,
    testrig_id,
    -- normalized location
    CASE
      WHEN lower(raw_location) LIKE '%bap%' THEN 'BaP'
      WHEN lower(raw_location) LIKE '%rng%' THEN 'RnG'
      WHEN lower(raw_location) LIKE '%tbp%' THEN 'TbP'
      WHEN lower(raw_location) LIKE '%liz%' THEN 'Liz'
      WHEN lower(raw_location) LIKE '%fz j%' THEN 'External'
      WHEN lower(raw_location) IN ('avl', 'kst', 'hycenta') THEN 'External'
      ELSE raw_location
    END AS location,
    -- UI label
    CONCAT(
      testrig_id,
      ' - ',
      CASE
        WHEN lower(raw_location) LIKE '%bap%' THEN 'BaP'
        WHEN lower(raw_location) LIKE '%rng%' THEN 'RnG'
        WHEN lower(raw_location) LIKE '%tbp%' THEN 'TbP'
        ELSE 'External'
      END
    ) AS testrig_label,
    -- sample label
    CASE
      WHEN sample_state IS NULL THEN sample_type
      ELSE CONCAT(sample_type, ' - ', sample_state)
    END AS sample_type_state,
    number_of_cells,
    -- hourly operational runtime
    CASE
      WHEN iStck > 0.1 THEN 1.0
      ELSE 0.0
    END AS run_hour
  FROM
    base
)
SELECT
  year,
  testrig_id,
  testrig_label,
  location,
  sample_type_state,
  number_of_cells,
  SUM(run_hour) AS run_hours
FROM
  filtered
GROUP BY
  year,
  testrig_id,
  testrig_label,
  location,
  sample_type_state,
  number_of_cells