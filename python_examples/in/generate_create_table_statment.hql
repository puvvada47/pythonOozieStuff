select distinct
    'CREATE TABLE `' || table_name || '` ('
from
    ${hivevar:v_db_name}.${hivevar:v_metatable_name}
where
    table_name = '${hivevar:v_tbl_name}'
union all
select concat_ws(',', collect_list(final_data_type))  from
(select '    `' || column_name || '` ' || case
    when data_type = 'NUMBER' then 'decimal(' || cast(data_precision as int) || ',' || cast(data_scale as int) || ')'
    when data_type in ('VARCHAR2') then 'VARCHAR(' || char_length || ') '
    else 'string '
    end as final_data_type
from
    ${hivevar:v_db_name}.${hivevar:v_metatable_name}
where
    data_type not in ('CLOB', 'BLOB', 'XMLTYPE', 'RAW')
    and table_name = '${hivevar:v_tbl_name}' order by column_id) as t1
union all
select ') STORED AS TEXTFILE;';
