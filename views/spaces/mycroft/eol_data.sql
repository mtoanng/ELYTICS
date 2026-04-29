with T1 AS
(SELECT * ,
CASE
      WHEN setpoint_direction='UI up' THEN eol_results.j_set
      WHEN setpoint_direction= 'UI down' THEN -eol_results.j_set
END AS j_set_plot
FROM ps_xplatform_dev.pemely_ops.gold_mfg_eol_results  eol_results
WHERE eol_results.step <= 28
)
,
T2 AS
(
SELECT * FROM 
(SELECT 
      max(int(step)) AS max_step, 
      first(test_type) as test_type,
      uniquepart_id,
      result_date_local_ts,
      process_number
FROM T1
GROUP BY uniquepart_id, process_number, result_date_local_ts)
WHERE 
        (max_step = 27 AND test_type='EOL: Polecurve1') OR 
        (max_step = 28 AND test_type='EOL: Polecurve2') OR 
        test_type='EOL: Pressure Operation Test' OR
        test_type='EOL: Startup'
)

SELECT T1.* FROM T1 
INNER JOIN T2
ON T1.uniquepart_id = T2.uniquepart_id AND T1.process_number = T2.process_number AND T1.result_date_local_ts = T2.result_date_local_ts
--WHERE stack_short_nr = 'P1_1250_160_05'