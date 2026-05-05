SELECT 
      sample,
      number_of_cells,
      stack_short_nr,
      uniquepart_id,
      plant,
      TO_DATE(production_date, 'yyMMdd') AS date,
      ROW_NUMBER() OVER(PARTITION BY stack_short_nr ORDER BY production_date ASC) AS sq_asc, --1 = first occurence
      ROW_NUMBER() OVER(PARTITION BY stack_short_nr ORDER BY production_date DESC) AS sq_desc, --1 = last occurence
      LEFT(stack_short_nr,2) AS proto,
      CONCAT(LEFT(stack_short_nr,2), ', ',CAST(number_of_cells AS STRING),' cell') AS identifier,
      LEFT(production_date,2) AS year,
      SUBSTR(production_date,3,2) AS month,
      SUBSTR(production_date,5,2) AS day
FROM ps_xplatform_dev.pemely_dev.silver_mfg_stack