WITH 
sample_selected AS (
  SELECT 
    sample_id, 
    name, 
    number_of_cells,
    active_area_per_cell, 
    ccm_name, 
    ccm_thickness
  FROM ps_xplatform_dev.pemely_ops.gold_sample
),
event_selected AS (
  SELECT
    event_id,
    order_id,
    start,
    sample_id
  FROM
    ps_xplatform_dev.pemely_ops.gold_polarization_event
),
order_selected AS (
  SELECT
    order_id,
    testrig_id,
    sample_name,
    sample_id
  FROM
    ps_xplatform_dev.pemely_ops.gold_genericstack_order
)
SELECT
  o.order_id,
  o.sample_name,
  o.testrig_id,
  e.event_id,
  s.name,
  s.number_of_cells,
  s.active_area_per_cell,
  s.ccm_name,
  s.ccm_thickness
FROM
  event_selected e
    INNER JOIN order_selected o
      ON e.order_id = o.order_id
    INNER JOIN sample_selected s
      ON o.sample_id = s.sample_id
ORDER BY
  e.start