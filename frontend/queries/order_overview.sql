SELECT
  o.order_id,
  o.sample_name,
  o.number_of_cells,
  o.testrig_id,
  o.short_description,
  s.jStack_max,
  s.uCell_max,
  s.tAndeIn_max,
  s.tAndeOut_max,
  s.pCtdeOut_max,
  s.pAndeIn_max,
  s.vfAndeIn_max,
  t.timeFacTest,
  t.timeFacRun,
  t.startCnt,
  t.maxh2out,
  t.time_total,
  e.polcurve_count
FROM
  ps_xplatform_dev.pemely_ops.gold_genericstack_order o
INNER JOIN (
  SELECT 
    order_id,
    MAX(jStck_max) AS jStack_max, 
    MAX(uCell_max) AS uCell_max,
    MAX(tAndeIn_max) AS tAndeIn_max,
    MAX(tAndeOut_max) AS tAndeOut_max,
    MAX(pCtdeOut_max) AS pCtdeOut_max,
    MAX(pAndeIn_max) AS pAndeIn_max,
    MAX(vfAndeIn_max) AS vfAndeIn_max
  FROM 
    ps_xplatform_dev.pemely_ops.gold_genericstack_static
  GROUP BY
    order_id
) s
  ON o.order_id = s.order_id
LEFT JOIN (
  SELECT
    order_id,
    datediff(HOUR, min(time), max(time)) as time_total,
    CEIL(SUM(timeFacTest)) AS timeFacTest,
    CEIL(SUM(timeFacRun)) AS timeFacRun,
    sum(startCnt) as startCnt,
    max(mfH2Out) as maxh2out
  FROM
    ps_xplatform_dev.pemely_ops.gold_genericstack_timeseries_1hr
  GROUP BY
    order_id
) t
  ON o.order_id = t.order_id
LEFT JOIN (
  SELECT
    order_id,
    count(event_id) as polcurve_count
  FROM
    ps_xplatform_dev.pemely_ops.gold_genericstack_event
  WHERE
    event_type = 'ivcurve'
  GROUP BY
    order_id
) e
  ON o.order_id = e.order_id