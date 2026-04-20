SELECT
  s.name,
  s.leepa_number,
  s.type,
  s.state,
  s.production_plant,
  s.description,
  s.cellunit_name,
  s.ccm_name,
  s.ptl_name,
  s.gdl_name,
  s.active_area_per_cell,
  o.order_id
FROM
  ps_xplatform_dev.pemely_ops.gold_sample s
    INNER JOIN (
      SELECT
        sample_id,
        order_id
      FROM
        ps_xplatform_dev.pemely_ops.gold_genericstack_order
    ) o
      ON o.sample_id = s.sample_id