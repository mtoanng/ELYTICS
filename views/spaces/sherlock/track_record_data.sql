SELECT
  v.sample_name,
  t.order_id,
  hr.time,
  ROUND(
    SUM(hr.timeFacRun) OVER (
        PARTITION BY v.sample_name
        ORDER BY hr.time
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
      ),
    2
  ) AS hours_run,
  CAST(hr.uCell AS DECIMAL(10, 2)) AS uCell,
  CAST(hr.jStck AS DECIMAL(10, 2)) AS jStck,
  CAST(hr.uStck AS DECIMAL(10, 2)) AS uStck,
  CAST(hr.iStck AS DECIMAL(10, 2)) AS iStck,
  CAST(hr.tAndeOut AS DECIMAL(10, 2)) AS tAndeOut,
  CAST(hr.pCtdeOut AS DECIMAL(10, 2)) AS pCtdeOut,
  CAST(hr.concO2H2 AS DECIMAL(10, 2)) AS concO2H2,
  CAST(hr.concH2O2 AS DECIMAL(10, 2)) AS concH2O2
FROM
  ps_xplatform_prod.pemely_ops.holmes_sherlock_meta_track_record_view AS v
    INNER JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_order AS t
      ON v.sample_name = t.sample_name
    INNER JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_timeseries_1hr AS hr
      ON t.order_id = hr.order_id
ORDER BY
  v.sample_name,
  hr.time