WITH base_ts AS (
  SELECT
    ts.time AS time_ts,
    ts.order_id,
    -- Sensors (ADD NEW ONES HERE ONLY)
    ts.j,
    ts.u_cell_avg,
    ts.p_an_in,
    ts.p_cat_out,
    ts.t_an_in,
    ts.vf_an_in
  FROM
    ps_xplatform_prod.pemely_ops.gold_timeseries_1h ts
  WHERE
    1 = 1
    AND ts.j > 0.03 -- operational definition
    AND ts.order_id LIKE 'E%'
),
joined AS (
  SELECT
    b.time_ts,
    b.order_id,
    o.testrig_id,
    o.sample_name,
    tr.location AS raw_location,
    CASE
      WHEN lower(tr.location) LIKE '%bap%' THEN 'BaP'
      WHEN lower(tr.location) LIKE '%rng%' THEN 'RnG'
      WHEN lower(tr.location) LIKE '%tbp%' THEN 'TbP'
      WHEN lower(tr.location) IN ('avl', 'liz', 'kst', 'hycenta', 'fz j') THEN 'External'
      ELSE tr.location
    END AS testrig_location,
    CONCAT(
      o.testrig_id,
      ' - ',
      CASE
        WHEN lower(tr.location) LIKE '%bap%' THEN 'BaP'
        WHEN lower(tr.location) LIKE '%rng%' THEN 'RnG'
        WHEN lower(tr.location) LIKE '%tbp%' THEN 'TbP'
        WHEN lower(tr.location) IN ('avl', 'liz', 'kst', 'hycenta', 'fz j') THEN 'External'
        ELSE tr.location
      END
    ) AS testrig_label,
    -- sensors
    b.j,
    b.u_cell_avg,
    b.p_an_in,
    b.p_cat_out,
    b.t_an_in,
    b.vf_an_in
  FROM
    base_ts b
      INNER JOIN ps_xplatform_prod.pemely_ops.gold_order o
        ON b.order_id = o.order_id
      LEFT JOIN ps_xplatform_prod.pemely_dev.silver_dim_testrig tr
        ON o.testrig_id = tr.testrig_id
)
SELECT
  *
FROM
  joined