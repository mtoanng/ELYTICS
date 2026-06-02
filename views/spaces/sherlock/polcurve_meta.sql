WITH event_selected AS (
  SELECT
    event_id,
    order_id,
    start
  FROM
    ps_xplatform_dev.pemely_ops.vav1tb_gold_event
  WHERE event_type = 'ivcurve'
),
order_selected AS (
  SELECT
    order_id,
    testrig_id,
    sample_name
  FROM
    ps_xplatform_prod.pemely_ops.gold_order
)
SELECT
  o.order_id,
  o.sample_name,
  o.testrig_id,
  e.event_id
FROM
  event_selected e
    INNER JOIN order_selected o
      ON e.order_id = o.order_id
ORDER BY
  e.start