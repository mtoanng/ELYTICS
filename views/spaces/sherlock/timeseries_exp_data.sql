SELECT
  o.testrig_id,
  o.sample_name,
  o.number_of_cells,
  ts.*
FROM
  ps_xplatform_dev.pemely_ops.gold_genericstack_timeseries_1s ts
    INNER JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_order o
      ON ts.order_id = o.order_id