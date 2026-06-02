-- Runtime data (1)
SELECT
  ORDR.order_id AS order_id,
  first_value(SAMP.sample_id) AS sample_id,
  first_value(SAMP.name) AS sample_name,
  first_value(SAMP.leepa_number) AS leepa_number,
  first_value(SAMP.ccm_name) AS ccm_name,
  first_value(SAMP.active_area_per_cell) AS active_area_per_cell,
  first_value(SAMP.ptl_name) AS PTL_name,
  first_value(SAMP.gdl_name) AS GDL_name,
  MAX(TS.calc.time_run) AS total_runtime,
  MIN(TS.time) AS start_time,
  MAX(TS.time) AS end_time,
  last_value(ORDR.testrig_id) AS testrig_id,
  -- Raw location
  last_value(TR.location) AS raw_location,
  -- Normalized location
  last_value(
    CASE
      WHEN lower(TR.location) LIKE '%bap%' THEN 'BaP'
      WHEN lower(TR.location) LIKE '%rng%' THEN 'RnG'
      WHEN lower(TR.location) LIKE '%tbp%' THEN 'TbP'
      WHEN lower(TR.location) LIKE '%avl%' THEN 'External'
      WHEN lower(TR.location) LIKE '%liz%' THEN 'External'
      WHEN lower(TR.location) LIKE '%kst%' THEN 'External'
      WHEN lower(TR.location) LIKE '%hycenta%' THEN 'External'
      WHEN lower(TR.location) LIKE '%fz j%' THEN 'External'
      ELSE TR.location
    END
  ) AS location_norm,
  -- UI label
  last_value(
    CONCAT(
      ORDR.testrig_id,
      ' - ',
      CASE
        WHEN lower(TR.location) LIKE '%bap%' THEN 'BaP'
        WHEN lower(TR.location) LIKE '%rng%' THEN 'RnG'
        WHEN lower(TR.location) LIKE '%tbp%' THEN 'TbP'
        WHEN lower(TR.location) LIKE '%avl%' THEN 'External'
        WHEN lower(TR.location) LIKE '%liz%' THEN 'External'
        WHEN lower(TR.location) LIKE '%kst%' THEN 'External'
        WHEN lower(TR.location) LIKE '%hycenta%' THEN 'External'
        WHEN lower(TR.location) LIKE '%fz j%' THEN 'External'
        ELSE TR.location
      END
    )
  ) AS testrig_label
FROM
  ps_xplatform_prod.pemely_ops.gold_timeseries_1h TS
    LEFT JOIN ps_xplatform_prod.pemely_ops.gold_order ORDR
      ON TS.order_id = ORDR.order_id
    LEFT JOIN ps_xplatform_prod.pemely_ops.gold_sample SAMP
      ON ORDR.sample_id = SAMP.sample_id
    LEFT JOIN ps_xplatform_prod.pemely_dev.silver_dim_testrig TR
      ON ORDR.testrig_id = TR.testrig_id
GROUP BY
  ORDR.order_id
ORDER BY
  start_time