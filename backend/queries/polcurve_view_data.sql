-- Common Table Expressions to pre-select columns and calculate per-event temp_set for efficiency
WITH static_selected AS (
  SELECT order_id, is_static, start, end, uCell, jStck, tAndeIn, time
  FROM ps_xplatform_dev.pemely_ops.gold_genericstack_static
),
event_selected AS (
  SELECT event_id, order_id, start, end, is_rising
  FROM ps_xplatform_dev.pemely_ops.gold_polarization_event
),
order_selected AS (
  SELECT order_id, testrig_id, number_of_cells, active_area_per_cell, sample_name
  FROM ps_xplatform_dev.pemely_ops.gold_genericstack_order
),
-- Calculate the average tAndeIn for each event_id, rounded to nearest decade
event_temp_set AS (
  SELECT e.event_id,
         CAST(ROUND(AVG(s.tAndeIn) / 10.0) * 10 AS INT) AS temp_set_avg -- average tAndeIn per event_id, rounded to nearest decade
    FROM static_selected s
    JOIN event_selected e
      ON s.order_id = e.order_id
     AND s.start >= e.start
     AND s.end <= e.end
   WHERE e.is_rising IS NOT NULL
     AND s.is_static = true
   GROUP BY e.event_id
)
SELECT 
    s.order_id,
    o.sample_name,
    o.testrig_id,
    o.number_of_cells,
    o.active_area_per_cell,
    DATE(s.time) AS date,
    DATE_FORMAT(s.start, 'HH:mm:ss') AS start_time,
    DATE_FORMAT(s.end, 'HH:mm:ss') AS end_time,
    s.uCell,
    s.jStck,
    s.tAndeIn,
    ets.temp_set_avg AS tSp, -- constant per event_id
    COALESCE(e.event_id, 'not part of a pol curve') AS event_id,
    e.is_rising
FROM static_selected s
INNER JOIN event_selected e
  ON s.order_id = e.order_id
  AND s.start >= e.start
  AND s.end <= e.end
INNER JOIN order_selected o
  ON s.order_id = o.order_id
INNER JOIN event_temp_set ets
  ON e.event_id = ets.event_id -- join to get per-event temp_set
WHERE e.is_rising IS NOT NULL
  AND s.is_static = true
{extra_conditions}
ORDER BY s.start
