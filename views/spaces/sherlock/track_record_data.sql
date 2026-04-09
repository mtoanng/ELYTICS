WITH top_5 AS (
  SELECT
    sample_name
  FROM
    ps_xplatform_prod.pemely_ops.holmes_sherlock_meta_track_record_view
  WHERE
    is_top5 = TRUE
),
raw AS (
  SELECT
    gs.time,
    o.sample_name,
    o.number_of_cells,
    gs.jStck,
    CASE
      WHEN o.number_of_cells > 0 THEN gs.uStck / o.number_of_cells
      ELSE NULL
    END AS uCell,
    gs.tAndeOut,
    gs.pCtdeOut,
    gs.concO2H2,
    gs.concH2O2,
    gs.segment_length_s / 3600.0 AS segment_length_h
  FROM
    ps_xplatform_dev.pemely_ops.gold_genericstack_static gs
      INNER JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_order o
        ON gs.order_id = o.order_id
      INNER JOIN top_5 t
        ON t.sample_name = o.sample_name
),
sample_time AS (
  SELECT
    r.time,
    r.sample_name,
    MAX(r.number_of_cells) AS number_of_cells,
    AVG(r.uCell) AS uCell,
    AVG(r.concO2H2) AS concO2H2,
    AVG(r.concH2O2) AS concH2O2,
    AVG(r.jStck) AS jStck,
    AVG(r.tAndeOut) AS tAndeOut,
    AVG(r.pCtdeOut) AS pCtdeOut,
    SUM(r.segment_length_h) AS segment_length_h
  FROM
    raw r
  GROUP BY
    r.time,
    r.sample_name
)
SELECT
  s.time,
  s.sample_name,
  CAST(NULL AS STRING) AS order_id,
  s.number_of_cells,
  SUM(s.segment_length_h) OVER (
      PARTITION BY s.sample_name
      ORDER BY s.time
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS runtime_hour,
  s.uCell,
  s.concO2H2,
  s.concH2O2,
  s.jStck,
  s.tAndeOut,
  s.pCtdeOut
FROM
  sample_time s