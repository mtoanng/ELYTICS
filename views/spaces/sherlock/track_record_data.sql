select
  samp.name as sample_name,
  cond.time,
  cond.u_cell_avg,
  cond.u,
  cond.j,
  cond.p_cat_out,
  cond.t_an_in,
  cond.order_id,
  cond.calc,
  cond.calc.time_test / 3600 as time_test,
  cond.calc.time_run / 3600 as time_run
from
  ps_xplatform_dev.pemely_ops.vav1tb_gold_conditioning_event cond
  left join ps_xplatform_dev.pemely_ops.gold_sample samp
    on cond.sample_id = samp.sample_id
order by sample_name, cond.calc.time_run


