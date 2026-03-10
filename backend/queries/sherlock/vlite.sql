WITH 
sample_selected AS (
  SELECT sample_id, name, number_of_cells,active_area_per_cell, ccm_name, ccm_thickness
  FROM ps_xplatform_dev.pemely_ops.gold_sample
),
order_selected AS (
  SELECT order_id, testrig_id, sample_id
  FROM ps_xplatform_dev.pemely_ops.gold_genericstack_order
)
SELECT 
    o.order_id,
    s.name,
    o.testrig_id,
    s.number_of_cells,
    s.active_area_per_cell,
    s.ccm_name,
    s.ccm_thickness
FROM sample_selected s
INNER JOIN order_selected o
  ON s.sample_id = o.sample_id
WHERE 1 = 1
{{filters}}
{{sorting}}
{{limit}}
{{offset}}