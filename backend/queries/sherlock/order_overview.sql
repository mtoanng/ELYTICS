SELECT
  o.order_id,
  o.sample_name,
  o.number_of_cells,
  o.testrig_id,
  o.short_description,
  t.time_total,
  t.timeFacTest,
  t.timeFacRun,
  t.startCnt,
  e.polcurve_count,
  s.jStack_max,
  s.uCell_max,
  s.tAndeIn_max,
  s.tAndeOut_max,
  s.pCtdeOut_max,
  s.pAndeIn_max,
  s.vfAndeIn_max,
  t.maxh2out
FROM
  ps_xplatform_dev.pemely_ops.gold_genericstack_order o
INNER JOIN (
  SELECT 
    order_id,
    MAX(CASE WHEN jStck_max IS NOT NULL AND jStck_max != 'NaN' THEN jStck_max END) AS jStack_max, 
    MAX(CASE WHEN uCell_max IS NOT NULL AND uCell_max != 'NaN' THEN uCell_max END) AS uCell_max,
    MAX(CASE WHEN tAndeIn_max IS NOT NULL AND tAndeIn_max != 'NaN' THEN tAndeIn_max END) AS tAndeIn_max,
    MAX(CASE WHEN tAndeOut_max IS NOT NULL AND tAndeOut_max != 'NaN' THEN tAndeOut_max END) AS tAndeOut_max,
    MAX(CASE WHEN pCtdeOut_max IS NOT NULL AND pCtdeOut_max != 'NaN' THEN pCtdeOut_max END) AS pCtdeOut_max,
    MAX(CASE WHEN pAndeIn_max IS NOT NULL AND pAndeIn_max != 'NaN' THEN pAndeIn_max END) AS pAndeIn_max,
    MAX(CASE WHEN vfAndeIn_max IS NOT NULL AND vfAndeIn_max != 'NaN' THEN vfAndeIn_max END) AS vfAndeIn_max
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
WHERE 1 = 1
{{filters}}
{{sorting}}
{{limit}}
{{offset}};