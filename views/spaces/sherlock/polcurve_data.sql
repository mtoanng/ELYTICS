WITH static_selected AS (
  SELECT
    order_id,
    is_static,
    segment_start,
    segment_end,
    j,
    u_cell_avg,
    t_an_in,
    t_an_out,
    p_an_in,
    p_an_out,
    p_cat_in,
    p_cat_out,
    vf_an_in,
    time
  FROM
    ps_xplatform_prod.pemely_ops.gold_timeseries_wide_static
),
event_selected AS (
  SELECT
    event_id,
    order_id,
    start,
    end,
    event_subtype
  FROM
    ps_xplatform_dev.pemely_ops.vav1tb_gold_event
  WHERE event_type = 'ivcurve'
),
order_selected AS (
  SELECT
    order_id,
    testrig_id,
    number_of_cells,
    active_area_per_cell,
    sample_name
  FROM
    ps_xplatform_prod.pemely_ops.gold_order
),
-- Calculate the average t_an_in for each event_id, rounded to nearest decade
event_setpoints AS (
  SELECT
    e.event_id,
    CAST(ROUND(AVG(s.t_an_in) / 10.0) * 10 AS INT) AS temp_set_avg, -- average t_an_in per event_id, rounded to nearest decade
    CAST(ROUND(AVG(s.p_cat_out) / 5.0) * 5 AS INT) AS p_cat_out_avg_5 -- average p_cat_out per event_id, rounded to nearest 5
  FROM
    static_selected s
      JOIN event_selected e
        ON s.order_id = e.order_id
        AND s.segment_start >= e.start
        AND s.segment_end <= e.end
  WHERE
    e.event_subtype IS NOT NULL
    AND s.is_static = true
  GROUP BY
    e.event_id
)
SELECT
  s.order_id,
  o.sample_name,
  o.testrig_id,
  o.number_of_cells,
  o.active_area_per_cell,
  DATE(s.time) AS date,
  DATE_FORMAT(s.segment_start, 'HH:mm:ss') AS segment_start_time,
  DATE_FORMAT(s.segment_end, 'HH:mm:ss') AS segment_end_time,
  s.j,
  s.u_cell_avg,
  s.t_an_in,
  s.t_an_out,
  s.p_an_in,
  s.p_an_out,
  s.p_cat_in,
  s.p_cat_out,
  s.vf_an_in,
  esp.temp_set_avg AS tSp, -- constant per event_id
  esp.p_cat_out_avg_5 AS pCtSp, -- new column: avg p_cat_out rounded to nearest 5
  COALESCE(e.event_id, 'not part of a pol curve') AS event_id,
  e.event_subtype
FROM
  static_selected s
    INNER JOIN event_selected e
      ON s.order_id = e.order_id
      AND s.segment_start >= e.start
      AND s.segment_end <= e.end
    INNER JOIN order_selected o
      ON s.order_id = o.order_id
    INNER JOIN event_setpoints esp
      ON e.event_id = esp.event_id -- join to get per-event temp_set
WHERE
  e.event_subtype IS NOT NULL
  AND s.is_static = true