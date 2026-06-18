SELECT
  o.sample_name,
  o.number_of_cells,
  ts.*
FROM
  ps_xplatform_prod.pemely_ops.gold_timeseries_1s ts
    INNER JOIN ps_xplatform_prod.pemely_ops.gold_order o
      ON ts.order_id = o.order_id
