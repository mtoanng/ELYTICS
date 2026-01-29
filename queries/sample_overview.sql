SELECT
  s.sample_name,
  s.sample_leepa_number,
  s.sample_type,
  s.sample_state,
  s.sample_production_plant,
  s.cellname_description,
  s.cellname_name,
  s.ccm_name,
  s.ptl_name,
  s.gdl_name,
  s.sample_active_area_per_cell,
  o.order_id
FROM 
  ps_xplatform_dev.pemely_ops.gold_genericstack_sample s
INNER JOIN (
  SELECT 
    sample_id,
    order_id
  FROM 
    ps_xplatform_dev.pemely_ops.gold_genericstack_order
) o
ON
  o.sample_id = s.sample_id